# fixtures/

- `synthetic/` — synthetic vendor fixtures: deterministic seed, `SYNTHETIC` watermark, isolated namespace (`docs/adr/0004-synthetic-real-isolation.md`, `FR-VND-06`).
- `tender-snapshots/` — frozen real fixtures (one subdirectory per source — `etender/`, `worldbank/`, ...) backing empirical-contract connectors and their schema-drift detectors (`FR-TND-10`, `INT-01`, `INT-02`). A fixture change is how `schema_drift_event` gets exercised in tests — fixtures here are deliberately versioned, not just "sample data."

No fixtures exist yet — populated starting task 1.A (worker-connector).
