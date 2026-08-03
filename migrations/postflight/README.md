# Postflight checks

**Requirements:** `FR-PLT-12`, `DM-06`

Run after a migration's DDL is applied, before the ledger entry's `postflight_status` is set to `passed`. A postflight check for migration `NNNN` is named `NNNN_<same-description>.check` (exact tooling/format decided in 0.B).

A postflight check verifies the migration produced the expected result — e.g., an expected constraint now exists, a column has the expected type, a row-count invariant holds. A migration whose postflight fails is **not** treated as successfully applied for the purpose of the startup schema-version check (`migrations/README.md` rule 2), even though its DDL executed — the ledger records the failure and an operator must resolve it before startup will proceed on that schema version.

No postflight checks exist yet — none are needed until the first domain migration is written (Phase 1+).
