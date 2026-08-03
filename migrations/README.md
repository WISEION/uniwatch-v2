# Migration ledger — convention

**Requirements:** `FR-PLT-12`, `DM-06`, `P007` (regression), `P114` (regression)

This document is the contract. Actual migration tooling (the runner, CLI, dependency choice) is 0.B/backend-core scope and is not implemented yet — this task (0.A) only fixes the structure and the rules any tooling built later must follow.

## Why

v1 changed schema and ran backfills implicitly at application startup (P114). That made "is the schema what the running code expects" an unanswerable question at any given moment, and made backfills under load an uncontrolled failure surface. v2 makes both explicit, versioned, and separate from process startup.

## Rules (non-negotiable, `FR-PLT-12`, `DM-06`)

1. **The schema never changes as a side effect of application startup.** Startup only *reads* the current ledger version and compares it against the version the running code was built for.
2. **On a version mismatch, the application fails to start with a clear, specific error** (expected vs. actual version) — it never "auto-fixes" the schema (see acceptance criterion in PRD `FR-PLT-12`: "Старт приложения на несовпадающей схеме — отказ с понятной ошибкой, не автоправка").
3. **Migrations are versioned, forward-moving, and tracked in a ledger table** in the database itself (bootstrapped by `0000_ledger.sql`) — not inferred from file timestamps or ORM model diffing.
4. **Migrations are idempotent to apply-if-not-applied**: re-running the migration command on an already-migrated database is a no-op for already-applied versions (needed for the migration-rehearsal test in 0.D: upgrade on an empty AND a seeded DB, repeatable).
5. **Backfill is a separate operation from schema migration.** A schema migration may add a nullable column or a new table; populating historical rows is a distinct, explicitly invoked backfill job (worker job, not a migration script), so it can be paused/resumed/monitored independently of schema change (`DM-06`).
6. **Pre/postflight checks bracket every migration run:**
   - **Preflight** (`migrations/preflight/`): runs before any migration is applied. Checks invariants the migration assumes hold (e.g., no orphaned FK rows the new constraint would reject) and fails the run before touching schema if they don't. This is also the enforcement point for `FR-PLT-13`/`P007`: an invariant violation found here quarantines the affected area instead of being silently migrated over.
   - **Postflight** (`migrations/postflight/`): runs after a migration is applied. Verifies the resulting schema/data matches what the migration intended (row counts, constraint presence, checksum spot-checks) before the ledger entry is marked `applied` rather than `failed`.
7. **Numbering:** `NNNN_short_description.sql`, four-digit zero-padded, monotonically increasing, never reused or renumbered even if a migration is later found to be wrong (write a new corrective migration instead — same discipline as ADRs).

## Layout

```text
migrations/
  README.md              this file
  0000_ledger.sql         bootstrap: creates the ledger table itself
  NNNN_<description>.sql  one file per migration, forward-only
  preflight/
    README.md             preflight check convention + naming
  postflight/
    README.md             postflight check convention + naming
```

## Ledger table (bootstrapped by `0000_ledger.sql`)

| Column | Purpose |
|---|---|
| `version` | migration number, primary key |
| `description` | human-readable, matches the filename's description |
| `checksum` | checksum of the migration file's contents, to detect a migration being edited after being applied |
| `applied_at` | timestamp |
| `applied_by` | identity/process that ran it |
| `preflight_status` / `postflight_status` | `passed` / `failed` / `skipped` — a migration with a `failed` postflight is not considered successfully applied even if the DDL itself ran |

## What is explicitly NOT decided by this document

- The migration runner/tool (Alembic or a hand-rolled runner) — 0.B decision, tracked when backend-core starts, not before.
- Any actual domain migration (tender/vendor/decision tables) — Phase 1+ scope, once the corresponding package's data model is designed against ADR-0003.
