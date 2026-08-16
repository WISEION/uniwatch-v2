# fixtures/

- `synthetic/` — synthetic vendor fixtures: deterministic seed, `SYNTHETIC` watermark, isolated namespace (`docs/adr/0004-synthetic-real-isolation.md`, `FR-VND-06`).
- `tender-snapshots/` — frozen real fixtures (one subdirectory per source — `etender/`, `worldbank/`, ...) backing empirical-contract connectors and their schema-drift detectors (`FR-TND-10`, `INT-01`, `INT-02`). A fixture change is how `schema_drift_event` gets exercised in tests — fixtures here are deliberately versioned, not just "sample data."
- `legacy-snapshots/` — contract document + synthetic worked example for the one allowed way legacy (v1) data enters this repo: a bounded, human-exported JSON snapshot consumed by `packages/tender/shadow_comparison.py` (FR-MIG-03, Phase 6 task 6.A). See `legacy-snapshots/README.md` for the exact shape and the synthetic-only rule.
