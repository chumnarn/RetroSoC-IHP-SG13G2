#!/usr/bin/env python3
"""Run the reviewed RetroSoC IHP130 full-chip flow with explicit gates."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shlex
import shutil
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


BASE_COMMIT = "7a58375c0bd7c24b98e36a5451288e0a0e5666dc"
PROFILE = "configs/ci/ihp130.mk"
ALL_STAGES = (
    "bootstrap",
    "preflight",
    "setup",
    "quality",
    "regression",
    "input",
    "doctor",
    "chip",
    "validate",
    "package",
)


class FlowError(RuntimeError):
    pass


def quote(command: list[str]) -> str:
    return " ".join(shlex.quote(item) for item in command)


def run_logged(
    command: list[str], *, cwd: Path, log: Path, env: dict[str, str], dry_run: bool
) -> None:
    print(f"+ {quote(command)}", flush=True)
    if dry_run:
        return
    log.parent.mkdir(parents=True, exist_ok=True)
    with log.open("w", encoding="utf-8", errors="replace") as output:
        process = subprocess.Popen(
            command,
            cwd=cwd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            errors="replace",
            bufsize=1,
        )
        assert process.stdout is not None
        for line in process.stdout:
            sys.stdout.write(line)
            output.write(line)
        returncode = process.wait()
    if returncode:
        raise FlowError(f"command failed with exit code {returncode}; log: {log}")


def output(command: list[str], *, cwd: Path, env: dict[str, str]) -> str:
    return subprocess.check_output(command, cwd=cwd, env=env, text=True).strip()


def load_activation(path: Path, env: dict[str, str]) -> dict[str, str]:
    result = subprocess.run(
        ["bash", "-c", 'source "$1"; env -0', "bash", str(path)],
        env=env,
        check=True,
        capture_output=True,
    )
    activated: dict[str, str] = {}
    for entry in result.stdout.split(b"\0"):
        if not entry or b"=" not in entry:
            continue
        name, value = entry.split(b"=", 1)
        activated[name.decode()] = value.decode(errors="surrogateescape")
    return activated


def resolve_python(value: str, env: dict[str, str], repo: Path, *, source: bool) -> str:
    if value != "auto":
        return str(Path(value).expanduser().resolve()) if "/" in value else value
    if source:
        candidate = repo / ".cache/retrosoc/development/venv/bin/python"
        if candidate.is_file():
            return str(candidate)
    found = shutil.which("python3", path=env.get("PATH"))
    if not found:
        raise FlowError("python3 is missing")
    return found


def make_command(args: argparse.Namespace, source_python: str, *extra: str) -> list[str]:
    return [
        "make",
        f"CONFIG={PROFILE}",
        f"BUILD_TIMESTAMP={args.build_timestamp}",
        f"JOBS={args.jobs}",
        f"PYTHON={source_python}",
        f"FLOW_PYTHON={source_python}",
        f"LIBRELANE_SOURCE_PYTHON={source_python}",
        f"LIBRELANE_PYTHON={args.resolved_librelane_python}",
        f"LIBRELANE_RUN_TAG={args.run_tag}",
        *extra,
    ]


def variant_root(args: argparse.Namespace, source_python: str, env: dict[str, str]) -> Path:
    text = output(make_command(args, source_python, "config"), cwd=args.repo, env=env)
    match = re.search(r"^VARIANT_ROOT\s+(.+)$", text, re.MULTILINE)
    if not match:
        raise FlowError("make config did not report VARIANT_ROOT")
    return Path(match.group(1)).resolve()


def require_patch(repo: Path) -> None:
    checks = {
        repo / "scripts/config_key.py": "TIMESTAMP_FORMAT.replace('%', '%%')",
        repo / "physical/librelane/mini/Makefile": "config.yaml",
        repo / "physical/librelane/mini/scripts/package.py": 'parser.add_argument("--run-tag"',
    }
    missing = [str(path) for path, marker in checks.items() if marker not in path.read_text()]
    if missing:
        raise FlowError("review patch is missing from: " + ", ".join(missing))


def preflight(args: argparse.Namespace, source_python: str, env: dict[str, str]) -> None:
    for command in ("git", "make", "bash"):
        if shutil.which(command, path=env.get("PATH")) is None:
            raise FlowError(f"required command is missing: {command}")
    head = output(["git", "rev-parse", "HEAD"], cwd=args.repo, env=env)
    if head != BASE_COMMIT and not args.allow_newer_commit:
        raise FlowError(f"expected RetroSoC {BASE_COMMIT}, found {head}")
    require_patch(args.repo)
    version = output(
        [source_python, "-c", "import sys; print('.'.join(map(str, sys.version_info[:3])))"],
        cwd=args.repo,
        env=env,
    )
    major_minor = tuple(int(item) for item in version.split(".")[:2])
    if major_minor != (3, 10) and not args.dry_run:
        raise FlowError(
            f"source-flow Python must be 3.10 for the locked pyslang wheel; found {version}"
        )
    output([source_python, str(args.repo / "scripts/config_key.py"), "--help"], cwd=args.repo, env=env)
    suffix = " (dry-run compatibility not enforced)" if args.dry_run else ""
    print(f"preflight passed: RetroSoC {head}, source Python {version}{suffix}")


def validate_outputs(args: argparse.Namespace, source_python: str, env: dict[str, str]) -> dict[str, object]:
    root = variant_root(args, source_python, env)
    run_root = root / "physical/librelane/mini/chip"
    required = [
        run_root / "config.yaml",
        run_root / "result.json",
        run_root / "final",
        run_root / "runs" / args.run_tag,
        root / "meta/manifest.json",
        root / "meta/librelane-chip-doctor.json",
        root / "meta/librelane-chip.json",
    ]
    missing = [str(path) for path in required if not path.exists()]
    if missing:
        raise FlowError("missing full-chip output(s): " + ", ".join(missing))
    doctor = json.loads((root / "meta/librelane-chip-doctor.json").read_text())
    result = json.loads((run_root / "result.json").read_text())
    if doctor.get("status") != "passed":
        raise FlowError("LibreLane doctor result is not passed")
    if result.get("status") != "passed" or result.get("exit_code") != 0:
        raise FlowError("LibreLane chip result is not passed")
    final_files = sorted(path for path in (run_root / "final").rglob("*") if path.is_file())
    extensions = {path.suffix.lower() for path in final_files}
    if ".gds" not in extensions or ".lef" not in extensions:
        raise FlowError("final views must contain at least GDS and LEF")
    return {
        "schema_version": 1,
        "status": "passed",
        "base_commit": BASE_COMMIT,
        "build_timestamp": args.build_timestamp,
        "run_tag": args.run_tag,
        "variant_root": str(root),
        "doctor": doctor,
        "chip_result": result,
        "final_file_count": len(final_files),
        "final_extensions": sorted(extensions),
    }


def package(args: argparse.Namespace, source_python: str, env: dict[str, str], log: Path) -> Path:
    root = variant_root(args, source_python, env)
    run_root = root / "physical/librelane/mini/chip"
    destination = run_root / f"retrosoc-ihp130-chip-{args.run_tag}.tar.gz"
    command = [
        source_python,
        str(args.repo / "physical/librelane/mini/scripts/package.py"),
        "--root",
        str(args.repo),
        "--variant-root",
        str(root),
        "--run-root",
        str(run_root),
        "--target",
        "chip",
        "--run-tag",
        args.run_tag,
        "--output",
        str(destination),
    ]
    run_logged(command, cwd=args.repo, log=log, env=env, dry_run=args.dry_run)
    return destination


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as source:
        while block := source.read(1024 * 1024):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repo", type=Path, required=True)
    parser.add_argument("--stages", default="preflight,setup,quality,regression,input,doctor,chip,validate,package")
    parser.add_argument("--build-timestamp", default=datetime.now(timezone.utc).strftime("%Y-%m-%d-%H-%M"))
    parser.add_argument("--run-tag", default="reviewed")
    parser.add_argument("--jobs", type=int, default=min(os.cpu_count() or 1, 16))
    parser.add_argument("--source-python", default="auto")
    parser.add_argument("--librelane-python", default="auto")
    parser.add_argument("--work-dir", type=Path)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--allow-newer-commit", action="store_true")
    args = parser.parse_args()
    args.repo = args.repo.resolve()
    probe = subprocess.run(
        ["git", "-C", str(args.repo), "rev-parse", "--git-dir"],
        check=False,
        capture_output=True,
    )
    if probe.returncode:
        parser.error(f"not a Git checkout: {args.repo}")
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]*", args.run_tag):
        parser.error("--run-tag must be one safe directory name")
    if args.jobs <= 0:
        parser.error("--jobs must be positive")
    stages = ALL_STAGES if args.stages == "all" else tuple(item.strip() for item in args.stages.split(",") if item.strip())
    unknown = sorted(set(stages) - set(ALL_STAGES))
    if unknown:
        parser.error("unknown stage(s): " + ", ".join(unknown))
    if not stages:
        parser.error("--stages must select at least one stage")
    work = (args.work_dir or Path.cwd() / "fullchip-work" / f"{args.build_timestamp}-{args.run_tag}").resolve()
    work.mkdir(parents=True, exist_ok=True)
    env = os.environ.copy()
    records: list[dict[str, str]] = []
    package_path: Path | None = None
    try:
        for index, stage in enumerate(stages, start=1):
            print(f"\n[{index}/{len(stages)}] {stage}", flush=True)
            log = work / "logs" / f"{index:02d}-{stage}.log"
            if stage == "bootstrap":
                run_logged(
                    [sys.executable, "scripts/development_environment.py", "bootstrap"],
                    cwd=args.repo,
                    log=log,
                    env=env,
                    dry_run=args.dry_run,
                )
                activation = args.repo / ".cache/retrosoc/development/activate.sh"
                if not args.dry_run:
                    env = load_activation(activation, env)
            source_python = resolve_python(args.source_python, env, args.repo, source=True)
            args.resolved_librelane_python = resolve_python(args.librelane_python, env, args.repo, source=False)
            if stage == "preflight":
                preflight(args, source_python, env)
            elif stage == "setup":
                run_logged(make_command(args, source_python, "setup"), cwd=args.repo, log=log, env=env, dry_run=args.dry_run)
            elif stage == "quality":
                run_logged([source_python, "-m", "ruff", "check", "."], cwd=args.repo, log=log.with_name(log.stem + "-ruff.log"), env=env, dry_run=args.dry_run)
                run_logged([source_python, "-m", "pytest", "-q"], cwd=args.repo, log=log.with_name(log.stem + "-pytest.log"), env=env, dry_run=args.dry_run)
            elif stage == "regression":
                for suffix, command in (
                    ("topology", make_command(args, source_python, "check-pin-map", "check-soc-topology", "check-clock-reset-domains")),
                    ("verilator", make_command(args, source_python, "SIMU=VERILATOR", "APP=ci_smoke", "sim")),
                    ("iverilog", make_command(args, source_python, "SIMU=IVERILOG", "RTL_SIM_TIMEOUT=5200000", "sim-asm")),
                    ("synth", make_command(args, source_python, "SYNTH=YOSYS", "synth")),
                    ("netsim", make_command(args, source_python, "SIMU=IVERILOG", "SIM_FIRMWARE_NAME=retrosoc_asm", "RTL_SIM_TIMEOUT=5200000", "netsim")),
                    ("sta", make_command(args, source_python, "STA=OPENSTA", "sta")),
                ):
                    run_logged(command, cwd=args.repo, log=log.with_name(log.stem + f"-{suffix}.log"), env=env, dry_run=args.dry_run)
            elif stage == "input":
                run_logged([source_python, "-c", "import pyslang"], cwd=args.repo, log=log.with_name(log.stem + "-pyslang.log"), env=env, dry_run=args.dry_run)
                run_logged(make_command(args, source_python, "librelane-input"), cwd=args.repo, log=log, env=env, dry_run=args.dry_run)
            elif stage == "doctor":
                run_logged(make_command(args, source_python, "librelane-doctor"), cwd=args.repo, log=log, env=env, dry_run=args.dry_run)
            elif stage == "chip":
                run_logged(make_command(args, source_python, "librelane-chip"), cwd=args.repo, log=log, env=env, dry_run=args.dry_run)
            elif stage == "validate" and not args.dry_run:
                report = validate_outputs(args, source_python, env)
                (work / "fullchip-validation.json").write_text(json.dumps(report, indent=2, sort_keys=True) + "\n")
            elif stage == "package":
                package_path = package(args, source_python, env, log)
            records.append({"stage": stage, "status": "planned" if args.dry_run else "passed", "log": str(log)})
    except (FlowError, OSError, subprocess.CalledProcessError, json.JSONDecodeError) as error:
        records.append({"stage": stage, "status": "failed", "error": str(error)})
        (work / "summary.json").write_text(json.dumps({"status": "failed", "records": records}, indent=2) + "\n")
        print(f"ERROR: {error}", file=sys.stderr)
        return 1
    summary: dict[str, object] = {"status": "planned" if args.dry_run else "passed", "records": records}
    if package_path and package_path.is_file():
        summary["package"] = str(package_path)
        summary["package_sha256"] = sha256_file(package_path)
    (work / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n")
    print(f"summary: {work / 'summary.json'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
