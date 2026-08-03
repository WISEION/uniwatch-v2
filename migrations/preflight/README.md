# Preflight checks

**Requirements:** `FR-PLT-13`, `P007`

Run before a migration's DDL is applied. A preflight check for migration `NNNN` is named `NNNN_<same-description>.check` (exact tooling/format decided in 0.B; the naming and ordering rule is fixed now: preflight for `NNNN` always runs, and must pass, before `NNNN`'s DDL executes).

A preflight check verifies the invariants the migration assumes hold — e.g., a migration that adds a `NOT NULL` FK constraint has a matching preflight check that scans for rows already violating it. If a preflight check fails, the migration does not run, and the affected data area is flagged for quarantine/read-only per `FR-PLT-13` — CI blocks on this (see `.ci/`).

No preflight checks exist yet — none are needed until the first domain migration is written (Phase 1+).
