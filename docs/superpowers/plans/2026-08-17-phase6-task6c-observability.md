# Phase 6 Task 6.C (Observability) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the observability module `docs/reports/PLAN-MISSION-6.md` §3 task 6.C requires — live operational signals, alert checks, incident runbooks, and an SLO-categories doc — as an independent module that reads existing tables, without blocking or being blocked by the API (per task 6.C's own framing: "parallel to 6.B, independent module").

**Architecture:** Each domain package (`packages/platform`, `packages/tender`, `packages/decision`, `packages/algorithm`) gains small, pure, read-only query functions for the signals it alone owns data for — no package imports a package "below" it in `AGENTS.md` §3's dependency direction (`packages/platform` never imports a domain package). Two new cross-cutting operator scripts (`scripts/collect_signals.py`, `scripts/check_alerts.py`) — the only place allowed to import across all of them, same precedent as `scripts/check_invariants.py`/`scripts/smoke_test.py` from task 6.B — aggregate those functions into one JSON payload and one alert gate, respectively. A new `restore_drill_runs` table (migration 0023) gives `docs/operations/runbook.md`'s step 3 (which already says a drill must be "performed and logged", but nothing ever implemented the logging) real evidence to check against.

**Tech stack:** No new runtime dependency. No metrics/Prometheus/OpenTelemetry library exists in this repo today (confirmed against `pyproject.toml`) and none is added — signals are exposed as plain JSON via a CLI script, matching this repo's existing scripts-based operational tooling (`scripts/check_invariants.py`, `scripts/smoke_test.py`) rather than introducing a dashboarding stack, since `D-HOST` (local-network-only pilot) and the absence of any chosen monitoring stack make that a real technology decision this plan does not invent — recorded as an assumption in Task 13.

## Global Constraints

- Never invent a number: SLO thresholds (`D-SLO`, `TBD-01`, `TBD-02`) stay unresolved placeholders everywhere in this plan — no code or doc introduces a numeric staleness/latency/RPO/RTO threshold.
- No silent fallback: any signal category with no real data source in this codebase (notification delivery, model drift/confidence/abstention, reconciliation-mismatch history) is reported as an explicit `"status": "not_applicable"` with a reason, never omitted and never fabricated.
- `packages/platform` never imports a domain package (`packages/tender`/`packages/decision`/`packages/algorithm`/`packages/vendor`) — cross-domain aggregation lives only in `scripts/*.py`.
- Every new DB-touching function takes an already-open `AsyncConnection` as its first positional/only connection argument, matching every existing `packages/*_store.py` function — no function opens its own connection except the two new top-level scripts' `main()`.
- Match existing SQL style exactly: `sqlalchemy.text()`, named `:param` binds, `.mappings().all()`/`.mappings().first()` for dict-shaped rows, `.scalar_one()` for single scalars.
- Run `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy packages apps scripts`, and `python tools/check_v1_untouched.py` after every task; all must stay clean.
- This machine's Docker/testcontainers instability is already documented (`docs/reports/WORKLOG.md`, 2026-08-16 entries) — if a local integration-test run hangs or is far slower than its CI counterpart, stop it and rely on CI's Full gate, per the same owner-approved precedent from tasks 6.A/6.B. Don't burn hours re-fighting known-flaky local Docker.

---

## Task 1: Migration 0023 (`restore_drill_runs`) + schema-version housekeeping

**Files:**
- Create: `migrations/0023_restore_drill_runs.sql`
- Modify: `packages/platform/settings.py:24`
- Modify: `tests/integration/test_api_tender_health.py:33`
- Modify: `tests/integration/test_api_vendor_health.py:34`
- Modify: `tests/integration/test_migrations_runner.py:26,27,35,56,125,126`

**Interfaces:**
- Produces: table `restore_drill_runs(id, backup_filename, target_database, passed, detail, drilled_at)`, `EXPECTED_SCHEMA_VERSION` default `23`.

- [ ] **Step 1: Write the migration**

```sql
-- Restore-drill evidence (Phase 6, task 6.C, NFR-REL-01 / master plan
-- §23.1's "backup age / restore drill age" line). docs/operations/runbook.md
-- step 3 already requires a restore drill to be "performed and logged" --
-- this is the first table that lets that actually be true. Append-only,
-- same discipline as deployment_authorizations/audit_log: a bad drill
-- result is not corrected by editing this row, only by running and
-- recording a new drill.
CREATE TABLE restore_drill_runs (
    id BIGSERIAL PRIMARY KEY,
    backup_filename TEXT NOT NULL,
    target_database TEXT NOT NULL,
    passed BOOLEAN NOT NULL,
    detail TEXT NOT NULL,
    drilled_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX restore_drill_runs_drilled_at_idx ON restore_drill_runs (drilled_at DESC, id DESC);
```

Save as `migrations/0023_restore_drill_runs.sql`.

- [ ] **Step 2: Bump `EXPECTED_SCHEMA_VERSION`**

In `packages/platform/settings.py:24`, change:

```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "22")))
```

to:

```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "23")))
```

- [ ] **Step 3: Update every hardcoded version-22 assertion**

`tests/integration/test_api_tender_health.py:33` and `tests/integration/test_api_vendor_health.py:34`: change `assert body["schema_version"] == 22` to `assert body["schema_version"] == 23`.

`tests/integration/test_migrations_runner.py`:
- Line 26: `assert versions == {1, 2, ..., 22}` → add `, 23` to the set literal.
- Line 27: `assert await runner.current_version() == 22` → `== 23`.
- Line 35: `assert await runner.current_version() == 22` → `== 23`.
- Line 56: `assert {m.version for m in applied} == {2, 3, ..., 22}` → add `, 23`.
- Line 125: `version = await assert_schema_up_to_date(asyncpg_dsn, MIGRATIONS_DIR, expected_version=22)` → `expected_version=23`.
- Line 126: `assert version == 22` → `== 23`.

- [ ] **Step 4: Run the migration test suite**

Run: `python -m pytest tests/integration/test_migrations_runner.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py -q`
Expected: all pass, confirming migration 0023 applies cleanly and every hardcoded version assertion is consistent.

- [ ] **Step 5: Commit**

```bash
git add migrations/0023_restore_drill_runs.sql packages/platform/settings.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py tests/integration/test_migrations_runner.py
git commit -m "feat(platform): add restore_drill_runs table (schema version 22->23)"
```

---

## Task 2: `packages/platform/restore_drill.py`

**Files:**
- Create: `packages/platform/restore_drill.py`
- Test: `tests/integration/test_restore_drill_log.py`

**Interfaces:**
- Consumes: `restore_drill_runs` table from Task 1.
- Produces: `record_restore_drill(conn: AsyncConnection, *, backup_filename: str, target_database: str, passed: bool, detail: str) -> int`, `latest_passing_drill(conn: AsyncConnection) -> dict[str, Any] | None`. Task 3 and Task 9 call these.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_restore_drill_log.py`:

```python
"""Restore-drill evidence log (Phase 6, task 6.C, NFR-REL-01)."""

from __future__ import annotations

from packages.platform.restore_drill import latest_passing_drill, record_restore_drill


async def test_latest_passing_drill_returns_none_when_no_drill_recorded(engine):
    async with engine.connect() as conn:
        result = await latest_passing_drill(conn)
    assert result is None


async def test_record_and_read_back_a_passing_drill(engine):
    async with engine.begin() as conn:
        drill_id = await record_restore_drill(
            conn,
            backup_filename="backup_20260817T000000Z.dump",
            target_database="uniwatch_drill",
            passed=True,
            detail="restored cleanly",
        )

    async with engine.connect() as conn:
        latest = await latest_passing_drill(conn)

    assert latest is not None
    assert latest["id"] == drill_id
    assert latest["backup_filename"] == "backup_20260817T000000Z.dump"
    assert latest["target_database"] == "uniwatch_drill"
    assert latest["passed"] is True
    assert latest["detail"] == "restored cleanly"


async def test_latest_passing_drill_ignores_failed_drills(engine):
    async with engine.begin() as conn:
        await record_restore_drill(
            conn,
            backup_filename="backup_20260817T010000Z.dump",
            target_database="uniwatch_drill",
            passed=False,
            detail="pg_restore exited 1",
        )

    async with engine.connect() as conn:
        result = await latest_passing_drill(conn)
    assert result is None


async def test_latest_passing_drill_returns_the_most_recent_pass(engine):
    async with engine.begin() as conn:
        await record_restore_drill(
            conn, backup_filename="backup_20260817T020000Z.dump", target_database="uniwatch_drill",
            passed=True, detail="first pass",
        )
        second_id = await record_restore_drill(
            conn, backup_filename="backup_20260817T030000Z.dump", target_database="uniwatch_drill",
            passed=True, detail="second pass",
        )

    async with engine.connect() as conn:
        latest = await latest_passing_drill(conn)

    assert latest is not None
    assert latest["id"] == second_id
    assert latest["detail"] == "second pass"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_restore_drill_log.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.platform.restore_drill'`.

- [ ] **Step 3: Write the implementation**

Create `packages/platform/restore_drill.py`:

```python
"""Restore-drill evidence (Phase 6, task 6.C, NFR-REL-01 / master plan
§23.1's "backup age / restore drill age" line): docs/operations/runbook.md's
step 3 already required a restore drill to be "performed and logged", but no
logging mechanism existed until this module -- every prior release relied on
an operator's unverifiable claim. Append-only, same discipline as
deployment_authorizations/audit_log: a bad drill result is not corrected by
editing this row, only by running and recording a new drill. Learned from
packages/platform/deployment_authorization.py's own bug fix: ORDER BY on a
`DEFAULT now()` timestamp column ties when multiple rows are written inside
one transaction (now() is transaction-start time in Postgres) -- `id DESC`
is included as a tiebreaker from the start here, not bolted on after a bug
report."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def record_restore_drill(
    conn: AsyncConnection,
    *,
    backup_filename: str,
    target_database: str,
    passed: bool,
    detail: str,
) -> int:
    row = (
        (
            await conn.execute(
                text(
                    """
                    INSERT INTO restore_drill_runs (backup_filename, target_database, passed, detail)
                    VALUES (:backup_filename, :target_database, :passed, :detail)
                    RETURNING id
                    """
                ),
                {
                    "backup_filename": backup_filename,
                    "target_database": target_database,
                    "passed": passed,
                    "detail": detail,
                },
            )
        )
        .mappings()
        .one()
    )
    return row["id"]


async def latest_passing_drill(conn: AsyncConnection) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, backup_filename, target_database, passed, detail, drilled_at
                    FROM restore_drill_runs
                    WHERE passed = TRUE
                    ORDER BY drilled_at DESC, id DESC
                    LIMIT 1
                    """
                )
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_restore_drill_log.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/platform/restore_drill.py tests/integration/test_restore_drill_log.py
git commit -m "feat(platform): add restore-drill evidence log"
```

---

## Task 3: `scripts/run_restore_drill.py`

**Files:**
- Create: `scripts/run_restore_drill.py`
- Test: `tests/integration/test_run_restore_drill.py`

**Interfaces:**
- Consumes: `scripts.backup.create_backup(database_url: str, output_dir: Path, *, filename: str | None = None) -> Path`, `scripts.restore.restore_backup(backup_path: Path, database_url: str) -> None` (raises `RestoreError`), `packages.platform.restore_drill.record_restore_drill`.
- Produces: `run_drill(source_database_url: str, drill_database_url: str, backup_dir: Path) -> int` (0 pass / 1 fail), CLI `main(argv) -> int`.

**Design note for the implementer:** the drill *backs up the source* and *restores into a second, disposable scratch database* (`drill_database_url` — never the source, never production) to prove the backup is actually restorable. The evidence row is written back into `source_database_url` (the environment being certified), not into the scratch drill target — `pg_restore` replaces the drill DB's entire contents each run, so a `restore_drill_runs` row written there would not survive the next drill. This mirrors why `tests/integration/test_restore_drill.py` (task 6.B) already restores into "a second, separate, never-migrated database" rather than the source.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_run_restore_drill.py`. Reuses the exact same "second, disposable database on the shared testcontainer" pattern `tests/integration/test_restore_drill.py` already established (its `restore_target_dsn` fixture + `_dsn_with_dbname` helper) — duplicated here under a different db-name prefix (own fixture, own file) rather than shared via `conftest.py`, so concurrent test runs never collide on the same scratch database name:

```python
"""Real restore-drill execution (Phase 6, task 6.C, NFR-REL-01). Backs up a
real seeded database, restores into a second real (never-migrated,
disposable) database -- same two-DB pattern as
tests/integration/test_restore_drill.py -- and confirms the result is
recorded back into the SOURCE database, not the scratch drill target
(pg_restore replaces the drill target's entire contents each run, which
would erase its own evidence row if recorded there instead)."""

from __future__ import annotations

import uuid
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import text

from packages.platform.restore_drill import latest_passing_drill
from scripts.run_restore_drill import run_drill


def _dsn_with_dbname(dsn: str, dbname: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest_asyncio.fixture
async def drill_target_dsn(_asyncpg_base_dsn):
    db_name = f"run_restore_drill_{uuid.uuid4().hex[:12]}"
    admin_conn = await asyncpg.connect(_asyncpg_base_dsn)
    try:
        await admin_conn.execute(f'CREATE DATABASE "{db_name}"')
    finally:
        await admin_conn.close()

    raw_dsn = _dsn_with_dbname(_asyncpg_base_dsn, db_name)
    try:
        yield raw_dsn
    finally:
        admin_conn = await asyncpg.connect(_asyncpg_base_dsn)
        try:
            await admin_conn.execute(f'DROP DATABASE IF EXISTS "{db_name}" WITH (FORCE)')
        finally:
            await admin_conn.close()


async def test_run_drill_records_a_passing_result_in_the_source_database(
    engine, _database_url, drill_target_dsn, tmp_path: Path
):
    async with engine.begin() as conn:
        await conn.execute(text("CREATE TABLE drill_probe (id INT PRIMARY KEY)"))
        await conn.execute(text("INSERT INTO drill_probe (id) VALUES (1)"))

    exit_code = await run_drill(
        source_database_url=_database_url,
        drill_database_url=drill_target_dsn,
        backup_dir=tmp_path,
    )

    assert exit_code == 0

    async with engine.connect() as conn:
        latest = await latest_passing_drill(conn)
    assert latest is not None
    assert latest["target_database"] == drill_target_dsn
    assert latest["backup_filename"].startswith("backup_")
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_run_restore_drill.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.run_restore_drill'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/run_restore_drill.py`:

```python
"""Executes a real restore drill (Phase 6, task 6.C, NFR-REL-01):
backs up `--source-database-url`, restores it into `--drill-database-url`
(a scratch database -- never the source or a production target; restoring
overwrites whatever the drill database currently holds), and records the
result in the SOURCE database via packages/platform/restore_drill.py --
not the drill database, since pg_restore replaces that database's entire
contents on the next run, which would erase its own evidence row.
docs/operations/runbook.md's step 3 (previously an unverifiable claim) reads
this table's latest passing row. Exits non-zero on any failure; a failed
drill is exactly the fact this script exists to catch, so it records a
`passed=False` row (never silently skips recording) before exiting non-zero.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from packages.platform.db import connection_scope, get_engine
from packages.platform.restore_drill import record_restore_drill
from scripts.backup import create_backup
from scripts.restore import RestoreError, restore_backup


async def run_drill(*, source_database_url: str, drill_database_url: str, backup_dir: Path) -> int:
    backup_path = create_backup(source_database_url, backup_dir)

    passed = True
    detail = f"restored {backup_path.name} into drill target successfully"
    try:
        restore_backup(backup_path, drill_database_url)
    except RestoreError as exc:
        passed = False
        detail = str(exc)

    engine = get_engine(source_database_url)
    try:
        async with connection_scope(engine) as conn:
            await record_restore_drill(
                conn,
                backup_filename=backup_path.name,
                target_database=drill_database_url,
                passed=passed,
                detail=detail,
            )
    finally:
        await engine.dispose()

    if not passed:
        print(f"[FAIL] restore drill: {detail}")
        return 1
    print(f"[PASS] restore drill: {detail}")
    return 0


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and record a UNIWatch v2 restore drill.")
    parser.add_argument("--source-database-url", required=True, help="the environment being certified as restorable")
    parser.add_argument("--drill-database-url", required=True, help="scratch database the backup is restored into")
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return await run_drill(
        source_database_url=args.source_database_url,
        drill_database_url=args.drill_database_url,
        backup_dir=args.backup_dir,
    )


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_run_restore_drill.py -q`
Expected: 1 passed. If PG client-version skew (documented in `docs/reports/WORKLOG.md` 2026-08-16) makes `restore_backup` fail locally, this is the same pre-existing local-environment gap task 6.B recorded — verify via CI instead, per this plan's Global Constraints note.

- [ ] **Step 5: Commit**

```bash
git add scripts/run_restore_drill.py tests/integration/test_run_restore_drill.py
git commit -m "feat(ops): add scripts/run_restore_drill.py"
```

---

## Task 4: `packages/platform/backup_signals.py`

**Files:**
- Create: `packages/platform/backup_signals.py`
- Test: `tests/unit/test_backup_signals.py`

**Interfaces:**
- Produces: `latest_backup_at(backup_dir: Path) -> datetime | None`. Task 9 calls this.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_backup_signals.py`:

```python
"""Backup-age signal (Phase 6, task 6.C, master plan §23.1's "backup age"
line). Pure filesystem scan -- no DB, no network -- so this belongs in
tests/unit/ per tests/README.md's Fast/Full split."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from packages.platform.backup_signals import latest_backup_at


def test_returns_none_when_directory_has_no_backup_files(tmp_path: Path):
    assert latest_backup_at(tmp_path) is None


def test_returns_none_when_directory_does_not_exist(tmp_path: Path):
    assert latest_backup_at(tmp_path / "does-not-exist") is None


def test_ignores_non_matching_filenames(tmp_path: Path):
    (tmp_path / "not-a-backup.txt").write_text("noise")
    (tmp_path / "backup_20260817T120000Z.dump.tmp").write_text("partial, wrong suffix")
    assert latest_backup_at(tmp_path) is None


def test_returns_the_newest_backup_timestamp(tmp_path: Path):
    (tmp_path / "backup_20260815T090000Z.dump").write_text("older")
    (tmp_path / "backup_20260817T120000Z.dump").write_text("newer")
    (tmp_path / "backup_20260816T030000Z.dump").write_text("middle")

    result = latest_backup_at(tmp_path)

    assert result == datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_backup_signals.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.platform.backup_signals'`.

- [ ] **Step 3: Write the implementation**

Create `packages/platform/backup_signals.py`:

```python
"""Pure backup-age signal (Phase 6, task 6.C, master plan §23.1's "backup
age" line). scripts/backup.py writes files named by its own
build_backup_filename() -- backup_<UTC timestamp>.dump -- and persists no DB
row (unlike a restore drill, a backup is not something later code needs to
query relationally; only "how old is the newest one" matters here). No new
table, just a filesystem scan; an empty/missing directory is a real,
surfaced state (None), never treated as "age zero" (hard ban #3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

_BACKUP_FILENAME_PREFIX = "backup_"
_BACKUP_FILENAME_SUFFIX = ".dump"
_BACKUP_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def latest_backup_at(backup_dir: Path) -> datetime | None:
    """Parses the UTC timestamp out of every `backup_<ts>.dump` filename in
    `backup_dir` (matching scripts/backup.py::build_backup_filename's exact
    format) and returns the newest, or None if the directory holds no
    matching file or does not exist. Reads the filename, not the file's
    mtime, so a copied/moved backup file (mtime reset by the copy) still
    reports its real backup time."""
    if not backup_dir.is_dir():
        return None

    newest: datetime | None = None
    for path in backup_dir.iterdir():
        if not (path.name.startswith(_BACKUP_FILENAME_PREFIX) and path.name.endswith(_BACKUP_FILENAME_SUFFIX)):
            continue
        timestamp_str = path.name[len(_BACKUP_FILENAME_PREFIX) : -len(_BACKUP_FILENAME_SUFFIX)]
        try:
            parsed = datetime.strptime(timestamp_str, _BACKUP_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            continue
        if newest is None or parsed > newest:
            newest = parsed
    return newest
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_backup_signals.py -q`
Expected: 4 passed.

- [ ] **Step 5: Commit**

```bash
git add packages/platform/backup_signals.py tests/unit/test_backup_signals.py
git commit -m "feat(platform): add pure backup-age signal"
```

---

## Task 5: Platform operational signals (`jobs.py`, `exception_queue.py`, `db_signals.py`)

**Files:**
- Modify: `packages/platform/jobs.py` (add two `JobStore` methods)
- Modify: `packages/platform/exception_queue.py` (add one function)
- Create: `packages/platform/db_signals.py`
- Modify: `tests/integration/test_jobs_store.py` (add tests)
- Modify: `tests/integration/test_exception_queue.py` (add tests)
- Test: `tests/integration/test_db_signals.py`

**Interfaces:**
- Produces: `JobStore.count_by_status(conn) -> dict[str, int]`, `JobStore.list_dead_lettered(conn) -> list[Job]`; `last_seen_by_source(conn: AsyncConnection, *, exception_type: str | None = None) -> dict[str, datetime]`; `connection_and_storage_signals(conn: AsyncConnection) -> dict[str, Any]` (keys: `active_connections`, `waiting_locks`, `database_size_bytes`). Task 9 and Task 10 call these.

- [ ] **Step 1: Write the failing tests for `JobStore`**

Append to `tests/integration/test_jobs_store.py`:

```python
async def test_count_by_status_reflects_real_rows(engine):
    store = JobStore()
    identity = JobIdentity(
        job_type="test_signal_job", params={}, source="test", range_start=None, range_end=None,
        contract_version="v1", correlation_id="corr-signal-1",
    )
    async with engine.begin() as conn:
        await store.enqueue(conn, identity)

    async with engine.connect() as conn:
        counts = await store.count_by_status(conn)

    assert counts.get("pending", 0) >= 1


async def test_list_dead_lettered_returns_only_terminally_failed_jobs(engine):
    store = JobStore()
    identity = JobIdentity(
        job_type="test_dead_letter_job", params={}, source="test", range_start=None, range_end=None,
        contract_version="v1", correlation_id="corr-signal-2",
    )
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, identity)
        claimed = await store.claim(conn, "worker-1", lease_seconds=60)
        assert claimed is not None and claimed.id == job_id
        for _ in range(claimed.max_attempts):
            status = await store.fail_retry(conn, job_id, "worker-1", "boom", backoff_seconds=0)
            if status == "failed":
                break
            await store.claim(conn, "worker-1", lease_seconds=60)

    async with engine.connect() as conn:
        dead = await store.list_dead_lettered(conn)

    assert any(job.id == job_id for job in dead)
    assert all(job.status == "failed" for job in dead)
```

Check the top of `tests/integration/test_jobs_store.py` already imports `JobIdentity`/`JobStore` — if not, add `from packages.platform.jobs import JobIdentity, JobStore` to its existing import line.

- [ ] **Step 2: Write the failing tests for `exception_queue`**

Append to `tests/integration/test_exception_queue.py`:

```python
async def test_last_seen_by_source_reflects_the_most_recent_event(engine):
    async with engine.begin() as conn:
        await enqueue_exception(
            conn, source="etender", exception_type="schema_drift", category="needs_human",
            reason="field removed", correlation_id="corr-signal-3",
        )

    async with engine.connect() as conn:
        seen = await last_seen_by_source(conn)

    assert "etender" in seen


async def test_last_seen_by_source_filters_by_exception_type(engine):
    async with engine.begin() as conn:
        await enqueue_exception(
            conn, source="worldbank_projects_api", exception_type="egress_rejected", category="retryable",
            reason="blocked host", correlation_id="corr-signal-4",
        )

    async with engine.connect() as conn:
        drift_only = await last_seen_by_source(conn, exception_type="schema_drift")

    assert "worldbank_projects_api" not in drift_only
```

Add `last_seen_by_source` to the existing `from packages.platform.exception_queue import ...` line at the top of the file.

- [ ] **Step 3: Write the failing test for `db_signals`**

Create `tests/integration/test_db_signals.py`:

```python
"""DB connections/locks/storage signal (Phase 6, task 6.C, master plan
§23.1)."""

from __future__ import annotations

from packages.platform.db_signals import connection_and_storage_signals


async def test_connection_and_storage_signals_returns_real_values(engine):
    async with engine.connect() as conn:
        signals = await connection_and_storage_signals(conn)

    assert signals["active_connections"] >= 1
    assert signals["waiting_locks"] >= 0
    assert signals["database_size_bytes"] > 0
```

- [ ] **Step 4: Run all three test files to verify they fail**

Run: `python -m pytest tests/integration/test_jobs_store.py tests/integration/test_exception_queue.py tests/integration/test_db_signals.py -q`
Expected: FAIL — `AttributeError: 'JobStore' object has no attribute 'count_by_status'`, `ImportError: cannot import name 'last_seen_by_source'`, `ModuleNotFoundError: No module named 'packages.platform.db_signals'`.

- [ ] **Step 5: Implement `JobStore` additions**

In `packages/platform/jobs.py`, add these two methods to the `JobStore` class (after `get`, using the existing `_JOB_COLUMNS` and `_row_to_job` helpers already defined above the class):

```python
    async def count_by_status(self, conn: AsyncConnection) -> dict[str, int]:
        rows = (await conn.execute(text("SELECT status, count(*) AS n FROM jobs GROUP BY status"))).all()
        return {row.status: row.n for row in rows}

    async def list_dead_lettered(self, conn: AsyncConnection) -> list[Job]:
        rows = (
            (
                await conn.execute(
                    text(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE status = 'failed' ORDER BY updated_at DESC")
                )
            )
            .mappings()
            .all()
        )
        return [_row_to_job(row) for row in rows]
```

- [ ] **Step 6: Implement `exception_queue.last_seen_by_source`**

In `packages/platform/exception_queue.py`, add `from datetime import datetime` to the imports, then add this function (near `list_open`):

```python
async def last_seen_by_source(conn: AsyncConnection, *, exception_type: str | None = None) -> dict[str, datetime]:
    """Source health signal (master plan §23.1's "source last success/
    failure/schema drift" line): every ingestion job that catches
    SchemaDriftDetected calls enqueue_exception(exception_type="schema_drift",
    ...), so this table is the only durable trail of drift/failure events
    per source -- packages/tender/schema_drift.py itself is pure and
    persists nothing. Pass exception_type="schema_drift" for drift-only
    history, or leave it None for "any exception queue entry, of any type,
    per source" (a broader failure signal)."""
    if exception_type is None:
        rows = (
            await conn.execute(
                text("SELECT source, max(first_seen_at) AS last_seen FROM exception_queue GROUP BY source")
            )
        ).all()
    else:
        rows = (
            await conn.execute(
                text(
                    "SELECT source, max(first_seen_at) AS last_seen FROM exception_queue "
                    "WHERE exception_type = :exception_type GROUP BY source"
                ),
                {"exception_type": exception_type},
            )
        ).all()
    return {row.source: row.last_seen for row in rows}
```

- [ ] **Step 7: Implement `db_signals.py`**

Create `packages/platform/db_signals.py`:

```python
"""DB connections/locks/storage signal (Phase 6, task 6.C, master plan
§23.1's "DB connections/locks/storage" line). Direct SQL against Postgres's
own catalog views -- pg_stat_activity/pg_locks/pg_database_size -- since no
domain table tracks this; this is the one signal category this module owns
because it has no natural home in any domain package."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def connection_and_storage_signals(conn: AsyncConnection) -> dict[str, Any]:
    active_connections = (
        await conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
    ).scalar_one()
    waiting_locks = (await conn.execute(text("SELECT count(*) FROM pg_locks WHERE NOT granted"))).scalar_one()
    database_size_bytes = (await conn.execute(text("SELECT pg_database_size(current_database())"))).scalar_one()
    return {
        "active_connections": active_connections,
        "waiting_locks": waiting_locks,
        "database_size_bytes": database_size_bytes,
    }
```

- [ ] **Step 8: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_jobs_store.py tests/integration/test_exception_queue.py tests/integration/test_db_signals.py -q`
Expected: all pass.

- [ ] **Step 9: Commit**

```bash
git add packages/platform/jobs.py packages/platform/exception_queue.py packages/platform/db_signals.py tests/integration/test_jobs_store.py tests/integration/test_exception_queue.py tests/integration/test_db_signals.py
git commit -m "feat(platform): add job queue, exception queue, and DB signal queries"
```

---

## Task 6: Tender pipeline signals (`raw_snapshot.py`, `boq_completeness.py`)

**Files:**
- Modify: `packages/tender/raw_snapshot.py` (add one function)
- Modify: `packages/tender/boq_completeness.py` (add one function)
- Modify: `tests/integration/test_raw_snapshot.py` (add tests)
- Modify: `tests/integration/test_boq_completeness.py` (add tests)

**Interfaces:**
- Produces: `last_fetched_at_by_source(conn: AsyncConnection) -> dict[str, datetime]`, `count_by_status(conn: AsyncConnection) -> dict[str, int]` (in `boq_completeness.py`). Task 9 and Task 10 call these.

- [ ] **Step 1: Write the failing test for `raw_snapshot`**

Append to `tests/integration/test_raw_snapshot.py` (check its existing imports for `save_raw_snapshot`'s exact keyword args and reuse them):

```python
async def test_last_fetched_at_by_source_reflects_the_most_recent_snapshot(engine):
    async with engine.begin() as conn:
        await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="design_tender",
            identity_key="signal-test-1",
            raw_body=b'{"a": 1}',
            contract_version="v1",
            correlation_id="corr-signal-5",
        )

    async with engine.connect() as conn:
        seen = await last_fetched_at_by_source(conn)

    assert "etender" in seen
```

Add `last_fetched_at_by_source` to the file's existing `from packages.tender.raw_snapshot import ...` line. If `save_raw_snapshot`'s real keyword names differ from the guess above, read the function's signature in `packages/tender/raw_snapshot.py` first and match it exactly — do not guess a second time.

- [ ] **Step 2: Write the failing test for `boq_completeness`**

Append to `tests/integration/test_boq_completeness.py`:

```python
async def test_count_by_status_reflects_real_rows(engine):
    async with engine.begin() as conn:
        await get_or_create_boq_import(conn, source="etender", event_id=999001)

    async with engine.connect() as conn:
        counts = await count_by_status(conn)

    assert counts.get("in_progress", 0) >= 1
```

Add `count_by_status` to the file's existing `from packages.tender.boq_completeness import ...` line.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_raw_snapshot.py tests/integration/test_boq_completeness.py -q`
Expected: FAIL — `ImportError: cannot import name 'last_fetched_at_by_source'` / `cannot import name 'count_by_status'`.

- [ ] **Step 4: Implement `raw_snapshot.last_fetched_at_by_source`**

In `packages/tender/raw_snapshot.py`, add `from datetime import datetime` to the imports, then add:

```python
async def last_fetched_at_by_source(conn: AsyncConnection) -> dict[str, datetime]:
    """Source freshness signal (master plan §23.1): the most recent
    fetched_at per source, across every raw_snapshots row ever captured --
    the only durable record of "when did this source last respond
    successfully". A failed fetch never reaches save_raw_snapshot, so a
    source's absence from this dict is itself meaningful: it has never
    succeeded (hard ban #3 -- surfaced, not hidden)."""
    rows = (
        await conn.execute(text("SELECT source, max(fetched_at) AS last_fetched FROM raw_snapshots GROUP BY source"))
    ).all()
    return {row.source: row.last_fetched for row in rows}
```

- [ ] **Step 5: Implement `boq_completeness.count_by_status`**

In `packages/tender/boq_completeness.py`, add:

```python
async def count_by_status(conn: AsyncConnection) -> dict[str, int]:
    """BOQ completeness signal (master plan §23.1): count of boq_import rows
    per status -- 'complete' / 'incomplete' / 'in_progress' /
    'source_exhausted_unverified' (INV-04's own status set, see hard ban
    #5 -- never invented, never collapsed into a binary complete/not)."""
    rows = (await conn.execute(text("SELECT status, count(*) AS n FROM boq_import GROUP BY status"))).all()
    return {row.status: row.n for row in rows}
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_raw_snapshot.py tests/integration/test_boq_completeness.py -q`
Expected: all pass.

- [ ] **Step 7: Commit**

```bash
git add packages/tender/raw_snapshot.py packages/tender/boq_completeness.py tests/integration/test_raw_snapshot.py tests/integration/test_boq_completeness.py
git commit -m "feat(tender): add source-freshness and BOQ-completeness signal queries"
```

---

## Task 7: Decision cycle-time signal (`decision_store.py`)

**Files:**
- Modify: `packages/decision/decision_store.py`
- Modify: `tests/integration/test_decision_store.py`

**Interfaces:**
- Produces: `list_decision_cycle_seconds(conn: AsyncConnection) -> list[dict[str, Any]]` (keys: `decision_id`, `tender_id`, `decision_type`, `decided_at`, `computed_at`, `cycle_seconds`). Task 9 calls this.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_decision_store.py`, reusing the file's real existing helpers verbatim: `_make_tender(conn, identity_key) -> int` and `_decision(tender_id, decision_type, decided_at) -> Decision` are already defined in this file (module scope); `BidReadinessCandidate`/`BoqMatchSummary`/`Decision` are already imported at the top of the file:

```python
async def test_list_decision_cycle_seconds_includes_a_decision_with_a_candidate(engine):
    summary = BoqMatchSummary(
        green_amount=Decimal("1000"), yellow_amount=Decimal("0"), red_amount=Decimal("0"),
        unpriced_line_count=0, non_matchable_line_count=0, non_matchable_amount=Decimal("0"),
        total_priced_amount=Decimal("1000"), green_pct=100.0, yellow_pct=0.0, red_pct=0.0,
    )
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-cycle-1")
        candidate = BidReadinessCandidate(
            tender_id=tender_id, summary=summary, is_lottery=False, critical_lines=(),
            computed_at="2026-08-08T00:00:00+00:00",
        )
        candidate_id = await store_bid_readiness_candidate(conn, candidate)
        decision = Decision(
            tender_id=tender_id, decision_type="bid", conditions=(), deadline=None,
            justification="test", actor="pm-1", decided_at="2026-08-09T00:00:00+00:00",
            go_no_go_inputs_id=None, bid_readiness_candidate_id=candidate_id,
        )
        await store_decision(conn, decision)

    async with engine.connect() as conn:
        cycles = await list_decision_cycle_seconds(conn)

    matching = [c for c in cycles if c["tender_id"] == tender_id]
    assert len(matching) == 1
    assert matching[0]["cycle_seconds"] == 86400.0  # exactly 1 day between computed_at and decided_at


async def test_list_decision_cycle_seconds_excludes_go_no_go_decisions(engine):
    # A decision with go_no_go_inputs_id instead of bid_readiness_candidate_id
    # (the _decision() helper's shape) has no candidate to time against and
    # must not appear.
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-cycle-2")
        await store_decision(conn, _decision(tender_id, "no_go", "2026-08-08T00:00:00+00:00"))

    async with engine.connect() as conn:
        cycles = await list_decision_cycle_seconds(conn)

    assert all(c["tender_id"] != tender_id for c in cycles)
```

Add `list_decision_cycle_seconds` to the file's existing `from packages.decision.decision_store import (...)` block.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_decision_store.py -k cycle_seconds -q`
Expected: FAIL with `ImportError: cannot import name 'list_decision_cycle_seconds'`.

- [ ] **Step 3: Write the implementation**

In `packages/decision/decision_store.py`, add:

```python
async def list_decision_cycle_seconds(conn: AsyncConnection) -> list[dict[str, Any]]:
    """Decision cycle-time signal (master plan §23.1): time from a Bid/
    No-Bid candidate's derived score (bid_readiness_candidates.computed_at,
    ADR-0003 layer 3) to the human decision that acted on it
    (decisions.decided_at, layer 4). Only decisions carrying a
    bid_readiness_candidate_id are included -- a go/no_go decision
    (go_no_go_inputs_id instead) has no candidate to time against, and is
    excluded rather than counted as a zero-length or missing cycle (hard
    ban #3). Override detection (did the human decision agree with the
    derived candidate) is deliberately NOT built here -- see
    docs/decisions/OPEN-QUESTIONS.md's 2026-08-17 entry for why, same
    precedent as task 5.C's list_case_traces()."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT d.id AS decision_id, d.tender_id, d.decision_type, d.decided_at,
                           c.computed_at, EXTRACT(EPOCH FROM (d.decided_at - c.computed_at)) AS cycle_seconds
                    FROM decisions d
                    JOIN bid_readiness_candidates c ON c.id = d.bid_readiness_candidate_id
                    WHERE d.bid_readiness_candidate_id IS NOT NULL
                    ORDER BY d.decided_at
                    """
                )
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_decision_store.py -q`
Expected: all pass, including the two new tests.

- [ ] **Step 5: Commit**

```bash
git add packages/decision/decision_store.py tests/integration/test_decision_store.py
git commit -m "feat(decision): add decision cycle-time signal query"
```

---

## Task 8: Policy version-usage signal (`policy_store.py`)

**Files:**
- Modify: `packages/algorithm/policy_store.py`
- Modify: `tests/integration/test_policy_store.py`

**Interfaces:**
- Produces: `list_all_active_versions(conn: AsyncConnection) -> list[dict[str, Any]]` (keys: `id`, `policy_graph_id`, `graph_name`, `version_number`, `status`, `created_by`, `created_at`). Task 9 calls this.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_policy_store.py`, reusing the file's real existing helper `_new_graph_draft_and_approve(conn, *, financial_impact=False, created_by="designer") -> tuple[int, int]` (already defined at module scope in this file — takes a draft graph all the way to `approved`) plus `activate_version` (already imported):

```python
async def test_list_all_active_versions_includes_a_real_active_version(engine):
    async with engine.begin() as conn:
        graph_id, version_id = await _new_graph_draft_and_approve(conn, created_by="signal-test-designer")
        await activate_version(conn, policy_version_id=version_id, changed_by="signal-test-approver")

    async with engine.connect() as conn:
        active_versions = await list_all_active_versions(conn)

    matching = [v for v in active_versions if v["policy_graph_id"] == graph_id]
    assert len(matching) == 1
    assert matching[0]["id"] == version_id
    assert matching[0]["status"] == "active"
    assert matching[0]["graph_name"] == "Bid/No-Bid -- Water Infrastructure"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_policy_store.py -k list_all_active_versions -q`
Expected: FAIL with `ImportError: cannot import name 'list_all_active_versions'`.

- [ ] **Step 3: Write the implementation**

In `packages/algorithm/policy_store.py`, add (near `list_versions_by_graph`):

```python
async def list_all_active_versions(conn: AsyncConnection) -> list[dict[str, Any]]:
    """Policy/model version-usage signal (master plan §23.1):
    list_versions_by_graph already answers "which versions does this one
    graph have" -- this is the cross-graph rollup an observability signal
    needs (every currently-active version, across every graph) without the
    caller enumerating every graph id first."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT pv.id, pv.policy_graph_id, pg.name AS graph_name, pv.version_number,
                           pv.status, pv.created_by, pv.created_at
                    FROM policy_versions pv
                    JOIN policy_graphs pg ON pg.id = pv.policy_graph_id
                    WHERE pv.status = 'active'
                    ORDER BY pg.name
                    """
                )
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_policy_store.py -q`
Expected: all pass.

- [ ] **Step 5: Commit**

```bash
git add packages/algorithm/policy_store.py tests/integration/test_policy_store.py
git commit -m "feat(algorithm): add cross-graph active-version signal query"
```

---

## Task 9: `scripts/collect_signals.py`

**Files:**
- Create: `scripts/collect_signals.py`
- Test: `tests/integration/test_collect_signals.py`

**Interfaces:**
- Consumes: every function produced by Tasks 2, 4, 5, 6, 7, 8.
- Produces: `collect_signals(database_url: str, backup_dir: Path) -> dict[str, Any]` (JSON-serializable), CLI `main(argv) -> int`.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_collect_signals.py`:

```python
"""Signal aggregation (Phase 6, task 6.C, master plan §23.1). Confirms every
signal category is present in the payload, including the honest
not_applicable entries for categories this repo has no real data source
for."""

from __future__ import annotations

from pathlib import Path

from scripts.collect_signals import collect_signals


async def test_collect_signals_returns_every_named_category(engine, _database_url, tmp_path: Path):
    payload = await collect_signals(_database_url, tmp_path)

    for key in (
        "job_queue", "exception_queue", "source_freshness", "boq_completeness",
        "decision_cycle", "policy_version_usage", "database", "restore_drill", "backup",
        "notification_delivery", "model_drift_confidence_abstention", "reconciliation_mismatches",
    ):
        assert key in payload, f"missing signal category: {key}"

    assert payload["notification_delivery"]["status"] == "not_applicable"
    assert payload["model_drift_confidence_abstention"]["status"] == "not_applicable"
    assert payload["reconciliation_mismatches"]["status"] == "not_applicable"
    assert payload["backup"]["latest_backup_at"] is None  # tmp_path has no backup files
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_collect_signals.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'scripts.collect_signals'`.

- [ ] **Step 3: Write the implementation**

Create `scripts/collect_signals.py`:

```python
"""Aggregates every observability signal this repo can honestly compute
today (Phase 6, task 6.C, master plan §23.1) into one JSON payload -- the
read side dashboards/alerts consume. Three of §23.1's named signal
categories have no real data source anywhere in this codebase and are
reported as such (`"status": "not_applicable"`, hard ban #3: no silent
fallback) rather than fabricated or silently dropped: notification_delivery
(no notifications table is created by any real migration --
packages/platform/invariant_checks.py's own no_orphaned_notifications found
the same gap), model_drift_confidence_abstention (no ML/model code exists
anywhere in this repo -- only rule/human policy-graph nodes; ml/hybrid node
types are schema-valid but rejected at construction), and
reconciliation_mismatches (packages/tender/shadow_comparison.py's classify
functions are pure and unpersisted -- no run-history table exists, per task
6.A's own record)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.algorithm.policy_store import list_all_active_versions
from packages.decision.decision_store import list_decision_cycle_seconds
from packages.platform.backup_signals import latest_backup_at
from packages.platform.db import connection_scope, get_engine
from packages.platform.db_signals import connection_and_storage_signals
from packages.platform.exception_queue import last_seen_by_source, list_open
from packages.platform.jobs import JobStore
from packages.platform.restore_drill import latest_passing_drill
from packages.platform.settings import get_settings
from packages.tender.boq_completeness import count_by_status as boq_count_by_status
from packages.tender.raw_snapshot import last_fetched_at_by_source

_NOT_APPLICABLE: dict[str, str] = {
    "notification_delivery": (
        "no notifications table is created by any real migration "
        "(see packages/platform/invariant_checks.py::no_orphaned_notifications)"
    ),
    "model_drift_confidence_abstention": (
        "no ML/model code exists in this repo; ml/hybrid policy nodes are schema-valid but rejected at construction"
    ),
    "reconciliation_mismatches": (
        "packages/tender/shadow_comparison.py classifications are pure and unpersisted; no run-history table exists"
    ),
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def collect_signals(database_url: str, backup_dir: Path) -> dict[str, Any]:
    engine = get_engine(database_url)
    job_store = JobStore()
    try:
        async with connection_scope(engine) as conn:
            payload: dict[str, Any] = {
                "job_queue": {
                    "by_status": await job_store.count_by_status(conn),
                    "dead_lettered_count": len(await job_store.list_dead_lettered(conn)),
                },
                "exception_queue": {
                    "open_count": len(await list_open(conn)),
                    "last_seen_by_source": await last_seen_by_source(conn),
                },
                "source_freshness": {
                    "last_fetched_at_by_source": await last_fetched_at_by_source(conn),
                },
                "boq_completeness": {
                    "by_status": await boq_count_by_status(conn),
                },
                "decision_cycle": {
                    "cycles": await list_decision_cycle_seconds(conn),
                },
                "policy_version_usage": {
                    "active_versions": await list_all_active_versions(conn),
                },
                "database": await connection_and_storage_signals(conn),
                "restore_drill": {
                    "latest_passing": await latest_passing_drill(conn),
                },
            }
    finally:
        await engine.dispose()

    payload["backup"] = {"latest_backup_at": latest_backup_at(backup_dir)}
    for key, reason in _NOT_APPLICABLE.items():
        payload[key] = {"status": "not_applicable", "reason": reason}

    return _jsonable(payload)


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect UNIWatch v2 observability signals as JSON.")
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    payload = await collect_signals(settings.database_url, args.backup_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_collect_signals.py -q`
Expected: 1 passed.

- [ ] **Step 5: Commit**

```bash
git add scripts/collect_signals.py tests/integration/test_collect_signals.py
git commit -m "feat(ops): add scripts/collect_signals.py observability aggregator"
```

---

## Task 10: Alerts (`packages/platform/alerts.py`, `packages/tender/freshness_alerts.py`, `scripts/check_alerts.py`)

**Files:**
- Create: `packages/platform/alerts.py`
- Create: `packages/tender/freshness_alerts.py`
- Create: `scripts/check_alerts.py`
- Test: `tests/integration/test_alerts.py`
- Test: `tests/integration/test_freshness_alerts.py`

**Interfaces:**
- Consumes: `JobStore.list_dead_lettered` (Task 5), `exception_queue.list_open` (existing), `invariant_checks.ALL_CHECKS` (existing, task 6.B), `raw_snapshot.last_fetched_at_by_source` (Task 6).
- Produces: `AlertResult(name: str, firing: bool, detail: str)` dataclass in `packages/platform/alerts.py`; `ALL_ALERTS: tuple[AlertCheck, ...]` in the same module; `source_never_succeeded(conn) -> AlertResult` in `packages/tender/freshness_alerts.py`.

- [ ] **Step 1: Write the failing tests for `packages/platform/alerts.py`**

Create `tests/integration/test_alerts.py`:

```python
"""Platform-scoped alert checks (Phase 6, task 6.C, NFR-OPS-02). Each check
is proven against both a healthy state (not firing) and a deliberately
provoked one (firing) -- same discipline as
tests/integration/test_invariant_checks.py."""

from __future__ import annotations

from packages.platform.alerts import (
    dead_lettered_jobs_present,
    exception_queue_has_open_items,
    invariant_violation_detected,
)
from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import JobIdentity, JobStore


async def test_dead_lettered_jobs_present_is_false_when_none_exist(engine):
    async with engine.connect() as conn:
        result = await dead_lettered_jobs_present(conn)
    assert result.firing is False


async def test_dead_lettered_jobs_present_fires_on_a_real_dead_letter(engine):
    store = JobStore()
    identity = JobIdentity(
        job_type="test_alert_job", params={}, source="test", range_start=None, range_end=None,
        contract_version="v1", correlation_id="corr-alert-1",
    )
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, identity)
        claimed = await store.claim(conn, "worker-1", lease_seconds=60)
        assert claimed is not None
        for _ in range(claimed.max_attempts):
            status = await store.fail_retry(conn, job_id, "worker-1", "boom", backoff_seconds=0)
            if status == "failed":
                break
            await store.claim(conn, "worker-1", lease_seconds=60)

        result = await dead_lettered_jobs_present(conn)

    assert result.firing is True
    assert str(job_id) in result.detail


async def test_exception_queue_has_open_items_is_false_when_empty(engine):
    async with engine.connect() as conn:
        result = await exception_queue_has_open_items(conn)
    assert result.firing is False


async def test_exception_queue_has_open_items_fires_on_a_real_open_item(engine):
    async with engine.begin() as conn:
        await enqueue_exception(
            conn, source="etender", exception_type="schema_drift", category="needs_human",
            reason="field removed", correlation_id="corr-alert-2",
        )
        result = await exception_queue_has_open_items(conn)
    assert result.firing is True


async def test_invariant_violation_detected_is_false_on_a_healthy_schema(engine):
    async with engine.connect() as conn:
        result = await invariant_violation_detected(conn)
    assert result.firing is False
```

- [ ] **Step 2: Write the failing test for `packages/tender/freshness_alerts.py`**

Create `tests/integration/test_freshness_alerts.py`:

```python
"""Source-freshness alert (Phase 6, task 6.C, NFR-OPS-02). Fires only on
"never fetched", a boolean condition -- not a staleness window, since
D-SLO/TBD-01/TBD-02 remain open (AGENTS.md hard ban #2)."""

from __future__ import annotations

from packages.tender.freshness_alerts import source_never_succeeded
from packages.tender.raw_snapshot import save_raw_snapshot


async def test_fires_when_no_source_has_ever_fetched(engine):
    async with engine.connect() as conn:
        result = await source_never_succeeded(conn)
    assert result.firing is True
    assert "etender" in result.detail
    assert "worldbank_projects_api" in result.detail


async def test_does_not_fire_once_every_known_source_has_fetched(engine):
    async with engine.begin() as conn:
        await save_raw_snapshot(
            conn, source="etender", resource_type="design_tender", identity_key="fresh-1",
            raw_body=b'{"a": 1}', contract_version="v1", correlation_id="corr-fresh-1",
        )
        await save_raw_snapshot(
            conn, source="worldbank_projects_api", resource_type="project", identity_key="fresh-2",
            raw_body=b'{"b": 2}', contract_version="v1", correlation_id="corr-fresh-2",
        )
        result = await source_never_succeeded(conn)
    assert result.firing is False
```

If `save_raw_snapshot`'s real keyword names differ from Task 6's guess, match the real signature from `packages/tender/raw_snapshot.py` here too.

- [ ] **Step 3: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_alerts.py tests/integration/test_freshness_alerts.py -q`
Expected: FAIL with `ModuleNotFoundError` for both `packages.platform.alerts` and `packages.tender.freshness_alerts`.

- [ ] **Step 4: Write `packages/platform/alerts.py`**

```python
"""Platform-scoped alert checks (Phase 6, task 6.C, NFR-OPS-02: freshness/
job-failure/invariant-violation/exception-queue-growth alerts). Each check
takes the same live AsyncConnection every packages/*_store.py module uses
and returns an AlertResult -- name/firing/detail, never a bare boolean
(hard ban #3: a firing alert is always actionable, not just "true").

Two of NFR-OPS-02's four categories cannot honestly carry a numeric
threshold yet -- D-SLO/TBD-01/TBD-02 remain open (AGENTS.md hard ban #2:
never invent a number) -- so `exception_queue_has_open_items` fires on "any
open row at all" (a genuinely boolean, threshold-free condition), not a
growth-rate window. True growth-rate detection would need a persisted
sample-history table this repo does not have; recorded as an honest gap in
docs/decisions/OPEN-QUESTIONS.md's 2026-08-17 entry, not approximated here.

Source-freshness alerting needs packages/tender-owned data (raw_snapshots)
and lives in packages/tender/freshness_alerts.py instead -- packages/platform
never depends on a domain package (AGENTS.md §3). scripts/check_alerts.py is
the one place both lists are combined."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncConnection

from .exception_queue import list_open
from .invariant_checks import ALL_CHECKS
from .jobs import JobStore


@dataclass(frozen=True)
class AlertResult:
    name: str
    firing: bool
    detail: str


AlertCheck = Callable[[AsyncConnection], Awaitable[AlertResult]]


async def dead_lettered_jobs_present(conn: AsyncConnection) -> AlertResult:
    dead = await JobStore().list_dead_lettered(conn)
    if dead:
        ids = ", ".join(str(job.id) for job in dead)
        return AlertResult(
            name="dead_lettered_jobs_present", firing=True, detail=f"{len(dead)} dead-lettered job(s): {ids}"
        )
    return AlertResult(name="dead_lettered_jobs_present", firing=False, detail="no dead-lettered jobs")


async def exception_queue_has_open_items(conn: AsyncConnection) -> AlertResult:
    open_items = await list_open(conn)
    if open_items:
        return AlertResult(
            name="exception_queue_has_open_items", firing=True, detail=f"{len(open_items)} open exception_queue row(s)"
        )
    return AlertResult(name="exception_queue_has_open_items", firing=False, detail="exception queue is empty")


async def invariant_violation_detected(conn: AsyncConnection) -> AlertResult:
    failing_names = []
    for check in ALL_CHECKS:
        result = await check(conn)
        if not result.passed:
            failing_names.append(result.name)
    if failing_names:
        return AlertResult(
            name="invariant_violation_detected", firing=True, detail=f"failing invariant(s): {', '.join(failing_names)}"
        )
    return AlertResult(name="invariant_violation_detected", firing=False, detail="all DB invariants pass")


ALL_ALERTS: tuple[AlertCheck, ...] = (
    dead_lettered_jobs_present,
    exception_queue_has_open_items,
    invariant_violation_detected,
)
```

- [ ] **Step 5: Write `packages/tender/freshness_alerts.py`**

```python
"""Source-freshness alert (Phase 6, task 6.C, NFR-OPS-02). Lives in
packages/tender, not packages/platform/alerts.py, because it reads
raw_snapshots (tender-owned) -- packages/platform never depends on a domain
package (AGENTS.md §3). Fires only on "this source has never successfully
fetched anything" -- a genuinely boolean, threshold-free condition -- not a
staleness window, since D-SLO/TBD-01/TBD-02 (the numeric freshness window)
remain open and this project never invents a number (AGENTS.md hard ban #2).

_KNOWN_SOURCES is a hardcoded list because no connector registry exists in
this codebase (each source is a fully separate, independently-added
connector module, per CLAUDE.md's tender-ingestion description) -- adding a
new connector requires adding its source string here too. Recorded as a
known limitation in docs/decisions/OPEN-QUESTIONS.md's 2026-08-17 entry, not
silently assumed to self-update."""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.alerts import AlertResult

from .raw_snapshot import last_fetched_at_by_source

_KNOWN_SOURCES = ("etender", "worldbank_projects_api")


async def source_never_succeeded(conn: AsyncConnection) -> AlertResult:
    seen = await last_fetched_at_by_source(conn)
    never_seen = [source for source in _KNOWN_SOURCES if source not in seen]
    if never_seen:
        return AlertResult(
            name="source_never_succeeded",
            firing=True,
            detail=f"source(s) with zero recorded fetches: {', '.join(never_seen)}",
        )
    return AlertResult(
        name="source_never_succeeded", firing=False, detail="every known source has at least one recorded fetch"
    )
```

- [ ] **Step 6: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_alerts.py tests/integration/test_freshness_alerts.py -q`
Expected: all pass.

- [ ] **Step 7: Write `scripts/check_alerts.py`**

```python
"""Live alert gate (Phase 6, task 6.C, NFR-OPS-02). Mirrors
scripts/check_invariants.py's shape exactly: runs every check in
packages/platform/alerts.py::ALL_ALERTS plus
packages/tender/freshness_alerts.py::source_never_succeeded against
DATABASE_URL and prints one line per check. Exits non-zero if any alert is
firing -- safe to wire into a periodic ops check the same way
check_invariants.py is wired into the post-deploy gate."""

from __future__ import annotations

import asyncio
import sys

from packages.platform.alerts import ALL_ALERTS
from packages.platform.db import connection_scope, get_engine
from packages.platform.settings import get_settings
from packages.tender.freshness_alerts import source_never_succeeded

_ALL_CHECKS = (*ALL_ALERTS, source_never_succeeded)


async def main() -> int:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    any_firing = False
    try:
        async with connection_scope(engine) as conn:
            for check in _ALL_CHECKS:
                result = await check(conn)
                status = "FIRING" if result.firing else "ok"
                print(f"[{status}] {result.name}: {result.detail}")
                if result.firing:
                    any_firing = True
    finally:
        await engine.dispose()

    if any_firing:
        print("one or more alerts are firing")
        return 1
    print("no alerts firing")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
```

No dedicated test for `scripts/check_alerts.py`'s `main()` — it is a thin CLI wrapper over already-tested `ALL_ALERTS`/`source_never_succeeded`, same precedent as `scripts/check_invariants.py` (untested `main`, tested `invariant_checks.py`).

- [ ] **Step 8: Commit**

```bash
git add packages/platform/alerts.py packages/tender/freshness_alerts.py scripts/check_alerts.py tests/integration/test_alerts.py tests/integration/test_freshness_alerts.py
git commit -m "feat(ops): add alert checks and scripts/check_alerts.py"
```

---

## Task 11: `docs/operations/slo.md`

**Files:**
- Create: `docs/operations/slo.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Write the SLO-categories doc**

Create `docs/operations/slo.md`:

```markdown
# SLO categories (Phase 6, task 6.C)

**Status:** Categories only — no numbers. `D-SLO` (`TBD-01`, `TBD-02`) is
open (`docs/decisions/OPEN-QUESTIONS.md`); master plan §23.3 is explicit
that numbers are approved only after a real load baseline, and
`AGENTS.md` hard ban #2 forbids substituting a "reasonable" default in the
meantime. This document exists so the categories master plan §23.3 names
have one canonical place to live before their numbers are decided — not to
pre-commit to a number by omission.

| Category | What it would bound | Where it's measured today (§23.1 signal) |
|---|---|---|
| Interactive p95 latency | Time to first byte for an interactive API route | Not instrumented yet — no request-latency middleware exists in `apps/api_tender`/`apps/api_vendor` (see `docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-17 entry) |
| Source freshness window | How old the last successful fetch from a source may be before it's "stale" | `scripts/collect_signals.py`'s `source_freshness.last_fetched_at_by_source`; `packages/tender/freshness_alerts.py::source_never_succeeded` only catches the zero-fetches case, not a staleness window |
| Job start/completion lag | Time from job enqueue to claim, and claim to completion | `scripts/collect_signals.py`'s `job_queue.by_status`; per-job timestamps are on the `jobs` row (`created_at`/`updated_at`) but no aggregate lag query exists yet |
| BOQ completeness target | What fraction of a tender's BOQ money must reconcile before treating it as usable | `scripts/collect_signals.py`'s `boq_completeness.by_status` |
| Availability | Fraction of time `/health/ready` reports `ok` | `packages/platform/app_factory.py`'s readiness probe; no uptime aggregation exists yet |
| Notification delay | Time from a triggering event to notification delivery | Not applicable today — no notifications mechanism exists in this repo (see `scripts/collect_signals.py`'s `notification_delivery` entry) |
| RPO/RTO | Maximum acceptable data loss / time to restore after an incident | `scripts/collect_signals.py`'s `restore_drill.latest_passing`/`backup.latest_backup_at` measure the *evidence* (when was this last proven); the *target* window is `D-SLO` |
| Incident acknowledgment | Time from an alert firing to a human acknowledging it | `scripts/check_alerts.py` produces the firing signal; no acknowledgment-tracking exists (would require a paging/on-call tool this pilot does not have, per `D-HOST`) |

**Do not add a number to this table** until `D-SLO` resolves — extend the
table with new categories as new signals are built, but leave the "target"
column absent rather than estimated.
```

- [ ] **Step 2: Commit**

```bash
git add docs/operations/slo.md
git commit -m "docs(ops): add SLO categories reference (no numbers, D-SLO open)"
```

---

## Task 12: Incident runbooks (`docs/operations/runbooks/`)

**Files:**
- Create: `docs/operations/runbooks/README.md`
- Create: `docs/operations/runbooks/source-schema-changed.md`
- Create: `docs/operations/runbooks/boq-reconciliation-failed.md`
- Create: `docs/operations/runbooks/worker-stuck-or-dead-letter.md`
- Create: `docs/operations/runbooks/database-invariant-failed.md`
- Create: `docs/operations/runbooks/restore-from-backup.md`
- Create: `docs/operations/runbooks/policy-model-kill-switch.md`
- Create: `docs/operations/runbooks/rollback-release.md`
- Create: `docs/operations/runbooks/suspected-credential-or-pii-incident.md`
- Create: `docs/operations/runbooks/vendor-tenant-isolation-incident.md`

**Interfaces:** none (docs only). These are the 9 incident-response runbooks master plan §23.4 names — distinct from `docs/operations/runbook.md`, which is a linear pre-release sequence, not an incident-response set (confirmed gap from research: none of the 9 existed as standalone docs before this task).

- [ ] **Step 1: Write the index**

Create `docs/operations/runbooks/README.md`:

```markdown
# Incident runbooks (master plan §23.4)

Nine incident-response runbooks, one per master-plan §23.4 category. These
are distinct from `docs/operations/runbook.md` (the linear pre-release
sequence for *running a release*) and `docs/operations/cutover-plan.md`
(the v1→v2 cutover/rollback decision) — each doc here is "this specific bad
thing just happened in a live environment, what do you do right now."

| Category (§23.4) | Runbook |
|---|---|
| Source schema changed | [source-schema-changed.md](source-schema-changed.md) |
| BOQ reconciliation failed | [boq-reconciliation-failed.md](boq-reconciliation-failed.md) |
| Worker stuck/dead letter | [worker-stuck-or-dead-letter.md](worker-stuck-or-dead-letter.md) |
| Database invariant failed | [database-invariant-failed.md](database-invariant-failed.md) |
| Restore from backup | [restore-from-backup.md](restore-from-backup.md) |
| Policy/model kill switch | [policy-model-kill-switch.md](policy-model-kill-switch.md) |
| Rollback release | [rollback-release.md](rollback-release.md) |
| Suspected credential/PII incident | [suspected-credential-or-pii-incident.md](suspected-credential-or-pii-incident.md) |
| Vendor tenant isolation incident | [vendor-tenant-isolation-incident.md](vendor-tenant-isolation-incident.md) |
```

- [ ] **Step 2: Write `source-schema-changed.md`**

```markdown
# Runbook: source schema changed

**Trigger:** `scripts/check_alerts.py`'s `exception_queue_has_open_items`
fires (or a manual `scripts/check_invariants.py`-adjacent look at
`exception_queue` shows a fresh row), and its `exception_type` is
`schema_drift`.

## What happened

One of `packages/tender`'s connectors (`etender_connector.py`,
`worldbank_connector.py`) called `packages/tender/schema_drift.py`'s
detection and it found the live source's response no longer matches that
connector's frozen `SourceContract`. Per `packages/tender`'s own
architecture (see `CLAUDE.md`), the job caught `SchemaDriftDetected` and
called `enqueue_exception(exception_type="schema_drift", category="needs_human", ...)`
instead of silently mapping the new shape — the response was **not**
ingested.

## Response

1. Query the open exception: `SELECT * FROM exception_queue WHERE exception_type = 'schema_drift' AND status = 'open' ORDER BY first_seen_at DESC;` — `reason`, `raw_ref`, and `correlation_id` identify exactly which contract failed and why.
2. Follow `raw_ref` to the `raw_snapshots` row (`packages/tender/raw_snapshot.py::get_raw_snapshot`) to see the actual raw response that triggered the drift.
3. Compare against the relevant `SourceContract` (`etender_contract.py`/`worldbank_contract.py`) to determine whether the source genuinely changed shape or a one-off malformed response occurred.
4. If the source genuinely changed: update the contract, add/adjust the connector's mapping, and add a regression test using the captured raw snapshot as a fixture — never edit the contract without a fixture that would have caught the drift.
5. Once fixed and merged/deployed, close the exception: `packages/platform/exception_queue.py::close_exception(conn, id=..., reason="contract updated in <PR>", closed_by="<your identity>")`.
6. If the ingestion job needs re-running for the affected range now that the contract is fixed, re-enqueue via the job's own `enqueue_*` entry point (per `packages/platform/jobs.py`'s job-identity model, a new range/params always gets a new job row, never a reused checkpoint).

## Do not

- Do not manually edit `exception_queue.status` to `'closed'` without following step 4/5 — that erases the actionable trail this table exists to preserve.
- Do not "fix" drift by loosening the contract to accept anything — a `SourceContract` exists specifically so an unexpected shape is caught, not silently absorbed (`AGENTS.md` hard ban #3).
```

- [ ] **Step 3: Write `boq-reconciliation-failed.md`**

```markdown
# Runbook: BOQ reconciliation failed

**Trigger:** `scripts/collect_signals.py`'s `boq_completeness.by_status`
shows a `boq_import` row stuck at `incomplete` or
`source_exhausted_unverified` for longer than expected, or
`packages/tender/boq_completeness.py::mark_import_stalled` was called for
a specific `(source, event_id)`.

## What happened

Per `INV-04` (`AGENTS.md` hard ban #5), a BOQ is `complete` only after
proven page/row reconciliation. `source_exhausted_unverified` means the
source ran out of pages to serve but never gave a total that would let
`boq_completeness.py` prove every page was actually fetched —
`incomplete` means fetching stopped (error, timeout, stall) before the
source was exhausted.

## Response

1. `SELECT * FROM boq_import WHERE status IN ('incomplete', 'source_exhausted_unverified') ORDER BY updated_at DESC;` to find the affected `(source, event_id)` rows. `missing_pages` and `page_checksums` show exactly what is/isn't accounted for.
2. For `incomplete`: check `exception_queue`/job logs for the underlying `bom_lines_job.py` run against that `(source, event_id)` — the stall/error reason lives there, not in `boq_import` itself.
3. Re-run the BOQ ingestion job for that specific `(source, event_id)` once the underlying cause (network, contract drift, rate limit) is resolved — `record_page_fetched` is idempotent per page, so a retry does not double-count already-fetched pages.
4. For `source_exhausted_unverified`: this is not automatically fixable — the source itself never provided a verifiable total. Confirm with a human reviewer whether the fetched lines are usable as-is (flagged, not silently treated as complete) before any downstream matching (`packages/decision/matching.py`) consumes this BOQ.

## Do not

- Do not manually set a `boq_import` row's `status` to `'complete'` to unblock downstream work — `INV-04` makes that a hard ban; `source_exhausted_unverified` is the honest terminal state when a source gives no way to prove completeness.
```

- [ ] **Step 4: Write `worker-stuck-or-dead-letter.md`**

```markdown
# Runbook: worker stuck or dead-lettered job

**Trigger:** `scripts/check_alerts.py`'s `dead_lettered_jobs_present`
fires, or `scripts/collect_signals.py`'s `job_queue.by_status` shows a
growing `leased` count with no matching `completed`/`failed` movement
(a worker likely died mid-lease without its lease expiring cleanly yet).

## What happened

`packages/platform/jobs.py`'s `fail_retry` moves a job to `'failed'`
(dead-lettered) only once `attempt >= max_attempts` — every retry before
that goes back to `'pending'` with an exponential backoff
(`compute_backoff_seconds`). A `'failed'` job has exhausted its retry
budget and needs a human, not another automatic attempt. A `'leased'` job
whose worker died keeps its row locked until `lease_expires_at` passes,
at which point `claim`'s own query already treats it as reclaimable
(`status = 'leased' AND lease_expires_at < now()`) — so a *stuck* worker
(long-running, not dead) looks identical to a live one until the lease
window elapses.

## Response

1. Dead-lettered: `SELECT * FROM jobs WHERE status = 'failed' ORDER BY updated_at DESC;` (or `packages/platform/jobs.py::JobStore.list_dead_lettered`). `last_error` holds the final failure reason; `checkpoint` holds however far it got.
2. Diagnose from `last_error` and `job_type`/`params`/`source`/`range_start`/`range_end` — the job's full identity is immutable from `enqueue` time (`FR-JOB-02`), so the exact input that failed is always reconstructible.
3. Once the underlying cause is fixed, do not resurrect the same row — per `FR-JOB-02`/`FR-JOB-06`, a job's identity is fixed at enqueue and never mutated. Enqueue a **new** job with the same `job_type`/`source`/range via that job type's own `enqueue_*` entry point.
4. Stuck-but-not-dead (`leased`, lease not yet expired, but no checkpoint progress for an unreasonable time): check the worker process (`apps/worker/main.py`) is actually alive and processing — if it's hung, kill the worker process; `claim`'s reclaim logic picks the job back up automatically once `lease_expires_at` passes, no manual row edit needed.

## Do not

- Do not manually `UPDATE jobs SET status = 'pending' WHERE id = ...` to force a retry — this bypasses the `attempt` counter and backoff bookkeeping `fail_retry` maintains, and can reintroduce a job past its intended `max_attempts`.
- Do not delete a dead-lettered row — it's the only record of what was attempted and why it failed.
```

- [ ] **Step 5: Write `database-invariant-failed.md`**

```markdown
# Runbook: database invariant failed

**Trigger:** `scripts/check_invariants.py` (or `scripts/check_alerts.py`'s
`invariant_violation_detected`) reports a `FAIL` line.

## What happened

One of `packages/platform/invariant_checks.py`'s live-DB structural checks
(`no_orphaned_notifications`, `policy_versions_one_active_per_graph`,
`no_orphaned_user_roles`) found the actual, currently-running database in a
state this project treats as structurally impossible — not a test-suite
finding against an ephemeral DB, a real finding against the real target.

## Response

1. Run `python scripts/check_invariants.py` directly against the affected environment's `DATABASE_URL` to get every failing check's `detail` (which rows, how many — never just "false", per hard ban #3).
2. `no_orphaned_user_roles` failing: a `users.role_id` points at a `roles` row that no longer exists. RBAC's deny-by-default resolution (`packages/platform/rbac/`) already treats an unresolvable role as no-access, so this is not an active security hole, but indicates a data-integrity bug (a role was deleted without reassigning its users) that needs a real fix, not just a one-off cleanup query.
3. `policy_versions_one_active_per_graph` failing: more than one `policy_versions` row is `status = 'active'` for the same `policy_graph_id` — the partial unique index this invariant checks should make this impossible via normal application code (`packages/algorithm/policy_store.py::activate_version`). Treat this as a serious finding — check for direct DB access outside the application (a manual `UPDATE`, a migration that bypassed the store) before assuming it's a code bug.
4. Do not write an ad hoc fix query without first reproducing how the bad state was reached — the same bug will recur otherwise. If a genuine application-code bug is found, treat it with the same priority as any other correctness bug in this codebase (test-first fix, per `AGENTS.md`).

## Do not

- Do not silence the check by removing rows without understanding root cause — this is a structural-integrity signal, not noise.
- Do not skip Gate 5 (post-deploy invariant check) on a future release "because it failed once and we understand why" — each release re-proves the invariant against that release's actual resulting state.
```

- [ ] **Step 6: Write `restore-from-backup.md`**

```markdown
# Runbook: restore from backup

**Trigger:** production data loss or corruption serious enough that the
fastest safe recovery is restoring from the last known-good backup, rather
than a forward fix.

**This is the disaster-recovery case — not the pre-release drill.** For
"confirm the restore mechanism still works before a release", see
`docs/operations/runbook.md` step 3 and `scripts/run_restore_drill.py`
(Phase 6, task 6.C) instead; this document is for an actual incident
against the real target database.

## Response

1. **Stop writes to the affected database immediately** — every additional write after the corrupting event narrows what a restore can recover, and some writes may themselves need to be replayed or discarded depending on what happened.
2. Identify the backup to restore: `scripts/collect_signals.py`'s `backup.latest_backup_at` and `restore_drill.latest_passing` tell you the newest backup's age and whether a drill has ever proven a restore from a recent backup actually works — prefer the most recent backup that has a passing drill on record, not merely the most recent file, if there's any doubt about a newer backup's integrity.
3. Run `python scripts/restore.py --backup-path <path> --database-url <target>` against the **real target** only after confirming step 1 and after getting the same distinct-approver sign-off `docs/operations/runbook.md`'s step 5 requires for a release — a restore is at least as consequential as a deploy and should not be a unilateral action.
4. After restore, run `python scripts/check_invariants.py` and `python scripts/smoke_test.py` (per `docs/operations/runbook.md` steps 4/7) against the restored database before declaring it live again.
5. Record what happened: what was lost (the gap between the backup's timestamp and the incident), why, and the restore's outcome — in `docs/reports/WORKLOG.md`, same append-only convention as every other operational event in this project.

## Do not

- Do not restore directly over a database still receiving writes without stopping them first — `pg_restore` against a live, write-receiving target can itself corrupt state further.
- Do not skip the invariant/smoke checks "to save time" — a restore that silently reintroduces a structural problem is worse than the outage it was meant to fix.
```

- [ ] **Step 7: Write `policy-model-kill-switch.md`**

```markdown
# Runbook: policy/model kill switch

**Trigger:** an active policy graph version (`packages/algorithm`) is
producing wrong/harmful decisions and needs to stop being used immediately.

## What happened / what to do

This project's only kill switch today is `packages/algorithm/policy_store.py::kill_switch`
(Phase 5, task 5.B — proven by
`tests/integration/test_policy_store.py::test_kill_switch_rehearsal_preserves_prior_journal_and_allows_reactivation`).
It is policy-graph-specific: there is no general job/worker emergency-stop
mechanism in this codebase (recorded as an honest gap in task 6.B's
WORKLOG entry — not built here either).

1. Identify the affected `policy_graph_id`/active `policy_version_id` — `scripts/collect_signals.py`'s `policy_version_usage.active_versions` lists every currently-active version across every graph.
2. Call `kill_switch` (via `apps/api_tender/routers/algoritm.py`'s HTTP surface, or directly against `packages/algorithm/policy_store.py` for an operator with DB access) against that version.
3. Confirm the version's status is no longer `active` and that `policy_version_transitions` recorded the change — per the 5.E rehearsal test, all prior transition history remains intact, byte-for-byte, and the version can be reactivated later once the underlying issue is fixed.
4. "Kill switch stops new evaluations" is interpreted as stopping future production routing — `packages/algorithm/simulation_engine.py`'s simulate/backtest endpoints intentionally remain usable against a killed version, so an analyst can still investigate what happened (this interpretation is recorded in task 5.E's WORKLOG entry, not re-decided here).
5. There is no production evaluation/routing engine in this codebase yet (same gap 5.B/5.C/5.E already recorded) — if a killed policy version was somehow still being consulted by a real decision path outside `packages/algorithm`'s own tested surface, that is itself a bug to find and fix, not something this runbook's kill switch alone resolves.

## Do not

- Do not delete or edit `policy_version_transitions` rows to "clean up" a kill event — it is the append-only rehearsal evidence this exact runbook's category exists to rely on.
```

- [ ] **Step 8: Write `rollback-release.md`**

```markdown
# Runbook: rollback release

**Trigger:** a just-deployed release is broken badly enough that the
fastest safe path is reverting to the prior release rather than
forward-fixing.

## Response

This runbook is a pointer, not a re-derivation: `docs/operations/runbook.md`
step 8 ("If step 3, 4, or 7 fails") already defines what happens when a
release's own post-deploy checks fail, and `docs/operations/cutover-plan.md`
defines rollback mechanics for the v1→v2 pilot specifically ("stop routing
to v2" — v2 never becomes the system of record during the pilot, so
rollback is a routing change, not a data-undo). Follow those two documents
directly:

1. `docs/operations/runbook.md` step 8 for the immediate "this release failed its own gate" sequence.
2. `docs/operations/cutover-plan.md` for what "stop routing to v2" means concretely in this pilot's topology (`D-HOST`: local network only).
3. If the release's problem involves data written since deploy that must not be lost, treat this as a `restore-from-backup.md` situation instead (or in addition) — a routing rollback alone does not undo bad writes already made against the new release's schema/logic.
4. Record the rollback and its cause in `docs/reports/WORKLOG.md`, same as every other operational event.

## Do not

- Do not re-derive a separate rollback mechanism here — this project already has two authoritative sources for it; a third, slightly different version would only create drift.
```

- [ ] **Step 9: Write `suspected-credential-or-pii-incident.md`**

```markdown
# Runbook: suspected credential/PII incident

**Trigger:** suspicion that a user credential (password hash, session
token) or personally-identifiable data was exposed, guessed, or accessed
outside normal authorized use.

## Response (mechanical steps only — this repo has no legal/compliance process to invent)

1. **Revoke the affected session(s) immediately**: `packages/platform/auth/session_store.py::revoke_session` for any specific session, or disable the account entirely via `apps/api_tender/routers/admin_users.py`'s disable endpoint (`packages/platform/audit.py::disable_user` — disable-not-delete, so the account's history remains for investigation).
2. **Force a password reset**: `admin_users.py`'s `POST /{id}/set-password` is the only way to set a password in this system — use it to set a new, operator-chosen password the affected user must then change; there is no self-service "forgot password" flow to fall back on.
3. **Check `failed_login_count`/`locked_until`** on the affected user row for evidence of a brute-force attempt (`migrations/0021_algoritm_local_auth.sql`'s lockout columns) — a pattern of failures just before the suspected incident is a real signal, not proof, of how access was obtained.
4. **Review the audit trail**: every admin action is appended to the audit log (`packages/platform/audit.py`) rather than mutating history — pull every audit entry for the affected account/actor around the suspected window.
5. **Note the cookie's TLS gap**: `apps/api_tender/routers/auth.py`'s session cookie is httpOnly but explicitly without `Secure` (TLS is out of scope for this pilot per `docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-15/16 entry) — if the suspected incident involves network interception rather than credential guessing/reuse, this is the most likely vector and is a known, previously-recorded gap, not a new one to silently patch here.
6. Record the incident, response, and outcome in `docs/reports/WORKLOG.md`.

## Do not

- Do not attempt to fabricate a formal legal/compliance breach-notification process here — no such process is defined anywhere in this project's source documents (`AGENTS.md` §1), and inventing one would itself violate hard ban #2's spirit (don't substitute an invented answer for a genuinely open decision).
```

- [ ] **Step 10: Write `vendor-tenant-isolation-incident.md`**

```markdown
# Runbook: vendor tenant isolation incident

**Trigger:** suspicion that one vendor-side tenant's data was exposed to,
or mutated by, another tenant/caller.

## What to check

`apps/api_vendor` uses a separate API-key mechanism for tenant isolation
(`D-IDP` explicitly does not extend session-based local auth to
`apps/api_vendor` — it has its own mechanism, per task 6.A's WORKLOG
entry). Per `AGENTS.md` §3 and ADR-0006, `packages/tender` never reads
`packages/vendor`'s internal tables directly — all cross-service access
goes through `packages/contracts/vendor_api.py`'s real network contract, so
a genuine isolation breach would show up as data crossing that boundary
incorrectly, not as an in-process leak.

1. Identify the affected API key(s)/tenant(s) and the specific `packages/vendor` records (vendors/offers) potentially exposed.
2. Every `Vendor`/`Offer` instance carries explicit `data_realm`/`watermark` fields (`packages/vendor/vendor_model.py`) — confirm whether the exposed records are `vendor-sandbox`/`SYNTHETIC` (the only realm this codebase currently produces, per ADR-0004) or something else; a `vendor-production`/`REAL` record existing at all would itself be a major finding, since nothing in this codebase produces real vendor data yet.
3. Check `apps/api_vendor/deps.py`'s API-key resolution and `apps/api_vendor/routers/internal.py`/`offers.py` for the actual query path that returned the exposed data — confirm whether tenant scoping was applied correctly in the query itself (missing a `WHERE tenant = ...` clause) versus an API-key validation bypass.
4. Revoke/rotate the affected API key(s) once the mechanism is identified.
5. Record the incident in `docs/reports/WORKLOG.md`, including whether any `REAL`-realm data was involved (which would also implicate the ADR-0004 synthetic/real isolation gate, a much larger issue than a single tenant leak).

## Do not

- Do not assume "it's all synthetic data anyway, low severity" without first confirming the `data_realm`/`watermark` fields on the actually-exposed records — check, don't assume.
```

- [ ] **Step 11: Commit**

```bash
git add docs/operations/runbooks/
git commit -m "docs(ops): add the 9 incident runbooks from master plan section23.4"
```

---

## Task 13: `docs/decisions/OPEN-QUESTIONS.md` entry

**Files:**
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

**Interfaces:** none (docs only). Append per `AGENTS.md` §4: "every deviation from PRD/master-plan, or new assumption, is recorded... never decided silently."

- [ ] **Step 1: Append the task 6.C entry**

Append to the end of `docs/decisions/OPEN-QUESTIONS.md` (read the file's existing entry format first — each dated entry already follows a Context/Assumptions/Owner-follow-up shape per the 6.A/6.B entries quoted in `docs/reports/WORKLOG.md` — match that shape):

```markdown
## 2026-08-17 — Task 6.C (observability)

**Context:** `PLAN-MISSION-6.md` §3 task 6.C — signals, runbooks, alerts, SLO categories, per master plan §23.

**Deviations/assumptions:**
1. No metrics/dashboarding technology (Prometheus, Grafana, OpenTelemetry) is chosen or added — signals are exposed as plain JSON via `scripts/collect_signals.py`, matching this repo's existing scripts-based ops tooling. `D-HOST` (local-network-only pilot) and the absence of any prior monitoring-stack decision make this a real open technology choice, not a locked one — revisit if/when a real dashboarding need arises.
2. Three of master plan §23.1's named signal categories have no real data source anywhere in this codebase and are reported as explicit `"status": "not_applicable"` rather than fabricated: `notification_delivery` (no `notifications` table exists — same gap task 6.B's `invariant_checks.py` already found), `model_drift_confidence_abstention` (no ML/model code exists anywhere in this repo), `reconciliation_mismatches` (`packages/tender/shadow_comparison.py` is pure/unpersisted, no run-history table).
3. `packages/tender/freshness_alerts.py`'s `_KNOWN_SOURCES` is a hardcoded tuple (`"etender"`, `"worldbank_projects_api"`) because no connector registry exists in this codebase — a new connector added later must also be added here, or its total-silence case won't be caught. Recorded, not silently assumed to self-update.
4. `exception_queue_has_open_items` (NFR-OPS-02's "growth" alert) fires on "any open item at all", not a true growth-rate/threshold — a real growth signal needs a persisted sample-history table (time series) that does not exist in this repo; this is a threshold-free proxy, not the thing NFR-OPS-02 literally asks for. Same for `source_never_succeeded`: fires only on zero-ever-fetches, not a staleness window, since `D-SLO`/`TBD-01`/`TBD-02` remain open.
5. Decision-cycle-time signal (`packages/decision/decision_store.py::list_decision_cycle_seconds`) deliberately does NOT attempt override/agreement classification (did the human decision agree with the derived candidate) — same precedent as task 5.C's `list_case_traces()`: comparing a decision's outcome against a candidate's derived verdict would be an invented heuristic, not a real one.
6. `restore_drill_runs` (migration 0023) is new persisted evidence that did not exist before this task — `docs/operations/runbook.md` step 3 already referenced "a restore drill... performed and logged" without any logging mechanism actually existing; this task builds that mechanism (`packages/platform/restore_drill.py`, `scripts/run_restore_drill.py`), it does not just observe a pre-existing one.
7. `docs/operations/slo.md`'s "interactive p95 latency" row is honestly marked "not instrumented yet" — no request-latency middleware exists in `apps/api_tender`/`apps/api_vendor`; adding one was judged out of this task's scope (it's a code change to the request path, not a read-only signal over existing data, unlike every other signal this task adds) and is left as a recorded gap rather than built speculatively.

**Source conflict (if any):** None.

**Owner follow-up needed:** No decision needed to consider 6.C's mechanism-building complete under the "categories, not numbers" framing master plan §23.3 itself specifies. `D-SLO`/`TBD-01`/`TBD-02` remain the actual blocker for turning `docs/operations/slo.md`'s categories into enforced thresholds — not addressed by this task, not supposed to be. If real dashboarding (not just JSON) becomes a pilot requirement, that is a new technology decision to make explicitly, not an extension of this task's scripts.
```

- [ ] **Step 2: Commit**

```bash
git add docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(decisions): record task 6.C assumptions and honest gaps"
```

---

## Final Step: Full verification and WORKLOG entry

After all 13 tasks are committed:

- [ ] Run `python -m pytest tests/ -q -m "not live_network"` — expect it to pass (rely on CI's Full gate if local Docker is unstable, per Global Constraints).
- [ ] Run `python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps scripts && python tools/check_v1_untouched.py` — expect all clean.
- [ ] Append a task 6.C entry to `docs/reports/WORKLOG.md` summarizing what was built, the honest gaps recorded in Task 13, and the exit-gate status for Phase 6 §4 relative to task 6.C's line items — same format as the 6.A/6.B entries already in that file.
- [ ] Open a PR (this repo's master is branch-protected — no direct push) and get it merged by a distinct approver from the initiator, per `AGENTS.md` hard ban #6/`INV-14`.
