# RetroSoC IHP SG13G2 Full Chip Quick Start

Run from this repository root on Ubuntu 22.04 x86-64 with Python 3.10.

```bash
export RETROSOC_ROOT="$PWD"
export BUILD_TIMESTAMP="$(date +%Y-%m-%d-%H-%M)"

python3 scripts/development_environment.py bootstrap
source .cache/retrosoc/development/activate.sh
make CONFIG=configs/ci/ihp130.mk SIMU=IVERILOG setup
```

Enter a LibreLane 3.0.5 environment, then run:

```bash
cd "$RETROSOC_ROOT"
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --source-python "$RETROSOC_ROOT/.cache/retrosoc/development/venv/bin/python" \
  --librelane-python "$(command -v python3)" \
  --build-timestamp "$BUILD_TIMESTAMP" \
  --run-tag full01 \
  --jobs 4 \
  --stages preflight,quality,regression,input,doctor,chip,validate,package
```

For a command-only rehearsal that does not launch EDA tools:

```bash
python3 scripts/run_fullchip.py \
  --repo "$RETROSOC_ROOT" \
  --source-python python3 \
  --librelane-python python3 \
  --run-tag dryrun \
  --stages all \
  --dry-run \
  --allow-newer-commit
```

The generated LibreLane file is below:

```text
build/<variant>/physical/librelane/mini/chip/config.yaml
```

Read `RetroSoC-Full-Chip-Manual-TH.md` before accepting any result. A clean
command exit is not sufficient: review the executed/skipped step list, SRAM
inventory, pad and PDN connectivity, all timing corners, DRC, LVS, antenna,
and final-view checksums. The baseline disables CTS and therefore is not a
post-CTS sign-off result.
