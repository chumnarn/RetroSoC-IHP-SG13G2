# RetroSoC IHP SG13G2 Ready Baseline

- RetroSoC upstream: `https://github.com/retroSoC/retroSoC`
- Upstream commit: `7a58375c0bd7c24b98e36a5451288e0a0e5666dc`
- IHP template reference: `https://github.com/IHP-GmbH/ihp-sg13g2-librelane-template`
- Template commit reviewed: `40ca8b9d5e8b3f87b2a36d590517958df21ee241`
- LibreLane: `3.0.5`
- PDK: `ihp-sg13g2`
- IHP Open PDK commit: `970a7688e7dcce2a6172797df9ef47bde2f60f9f`
- Profile: `configs/ci/ihp130.mk`
- Full-chip top: `retrosoc_asic`

This snapshot changes only build and delivery tooling: argparse help escaping,
the generated LibreLane filename (`config.yaml`), selected run-tag packaging,
tests, the staged runner, and documentation. It does not change RTL, the pin
map, SDC generation, macro placement, PDN topology, or locked dependencies.

The open-source flow is an implementation-development baseline. It is not a
foundry-qualified tape-out release. In particular, the current generated
configuration sets `RUN_CTS=false`; CTS and post-CTS timing closure remain an
explicit validation milestone.
