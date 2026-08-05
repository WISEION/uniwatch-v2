"""Migration ledger runner (FR-PLT-12, DM-06, P007, P114).

Talks to Postgres directly via `asyncpg` (not through the app's SQLAlchemy
engine) because migration files are plain multi-statement SQL scripts with
no bind parameters — asyncpg's `Connection.execute()` runs those as-is,
which the SQLAlchemy DBAPI layer does not support in one call.

Rules enforced here, matching `migrations/README.md`:
- The schema never changes as a side effect of application startup —
  `apply_all()` is only ever invoked by an explicit migration command/test
  fixture, never by `apps/api/main.py` or `apps/worker/main.py`.
- `current_version()` only reads the ledger; startup uses it to fail fast
  on a version mismatch instead of auto-fixing the schema.
- Migrations are idempotent to apply-if-not-applied: re-running `apply_all`
  on an already-migrated database is a no-op for already-applied versions.
- A migration whose file content changed after being applied (checksum
  mismatch) is a hard error, not silently re-applied.
- Preflight failure blocks the DDL from running at all (FR-PLT-13
  quarantine trigger point); postflight failure lets the DDL commit but
  marks the version as not-current, halting further migrations.
"""

from __future__ import annotations

import hashlib
from collections.abc import Awaitable, Callable
from dataclasses import dataclass
from pathlib import Path

import asyncpg

# ON CONFLICT ... DO UPDATE, not DO NOTHING: a version can already have a
# ledger row from an earlier quarantined attempt (pending() lets
# preflight-failed versions be retried), and that stale row must be
# overwritten, not left behind masking this attempt's outcome.
_LEDGER_UPSERT_SQL = """
    INSERT INTO schema_migrations
        (version, description, checksum, applied_by, preflight_status, postflight_status)
    VALUES ($1, $2, $3, $4, $5, $6)
    ON CONFLICT (version) DO UPDATE SET
        description = EXCLUDED.description,
        checksum = EXCLUDED.checksum,
        applied_at = now(),
        applied_by = EXCLUDED.applied_by,
        preflight_status = EXCLUDED.preflight_status,
        postflight_status = EXCLUDED.postflight_status
"""


@dataclass(frozen=True)
class Migration:
    version: int
    description: str
    path: Path
    checksum: str
    sql: str


@dataclass(frozen=True)
class AppliedMigration:
    version: int
    description: str


class MigrationChecksumMismatch(RuntimeError):
    def __init__(self, version: int):
        super().__init__(
            f"migration {version} was edited after being applied (checksum mismatch) — write a new corrective migration instead"
        )
        self.version = version


class PreflightFailed(RuntimeError):
    def __init__(self, version: int):
        super().__init__(f"migration {version} preflight failed — quarantined, not applied")
        self.version = version


class PostflightFailed(RuntimeError):
    def __init__(self, version: int):
        super().__init__(f"migration {version} postflight failed — DDL committed but not considered the current schema version")
        self.version = version


class SchemaVersionMismatch(RuntimeError):
    def __init__(self, expected: int | None, actual: int | None):
        super().__init__(
            f"schema version mismatch: application expects {expected}, ledger reports {actual} — refusing to start (FR-PLT-12)"
        )
        self.expected = expected
        self.actual = actual


PreflightHook = Callable[[asyncpg.Connection, Migration], Awaitable[bool]]
PostflightHook = Callable[[asyncpg.Connection, Migration], Awaitable[bool]]


class MigrationRunner:
    def __init__(self, dsn: str, migrations_dir: Path):
        self._dsn = dsn
        self._dir = migrations_dir

    def discover(self) -> list[Migration]:
        migrations = []
        for path in sorted(self._dir.glob("*.sql")):
            version_str, _, description = path.stem.partition("_")
            sql = path.read_text(encoding="utf-8")
            checksum = hashlib.sha256(sql.encode("utf-8")).hexdigest()
            migrations.append(Migration(int(version_str), description, path, checksum, sql))
        return migrations

    async def _connect(self) -> asyncpg.Connection:
        return await asyncpg.connect(self._dsn)

    async def _ensure_ledger(self, conn: asyncpg.Connection) -> None:
        bootstrap_path = self._dir / "0000_ledger.sql"
        await conn.execute(bootstrap_path.read_text(encoding="utf-8"))

    async def current_version(self, conn: asyncpg.Connection | None = None) -> int | None:
        owns_conn = conn is None
        if conn is None:
            conn = await self._connect()
        try:
            await self._ensure_ledger(conn)
            # A preflight-failed migration is recorded with postflight_status
            # 'skipped' (same value the version-0 bootstrap row uses, which
            # never goes through preflight/postflight at all) -- filtering on
            # postflight_status alone would count a quarantined migration
            # whose DDL never ran as "current", exactly the mismatch
            # FR-PLT-12 exists to prevent. Both failure kinds must be
            # excluded explicitly (found via the P007 regression test,
            # tests/integration/test_invariant_quarantine.py).
            return await conn.fetchval(
                "SELECT max(version) FROM schema_migrations WHERE preflight_status != 'failed' AND postflight_status != 'failed'"
            )
        finally:
            if owns_conn:
                await conn.close()

    async def pending(self) -> list[Migration]:
        migrations = [m for m in self.discover() if m.version != 0]
        conn = await self._connect()
        try:
            await self._ensure_ledger(conn)
            rows = await conn.fetch("SELECT version, checksum, preflight_status FROM schema_migrations")
        finally:
            await conn.close()
        # A preflight-failed row is a quarantined migration whose DDL never
        # ran -- it must stay eligible for retry once whatever it flagged is
        # fixed, not be treated as already applied just because a ledger row
        # exists for its version (found via the P007 regression test,
        # tests/integration/test_invariant_quarantine.py).
        applied = {row["version"]: row["checksum"] for row in rows if row["preflight_status"] != "failed"}

        result = []
        for m in migrations:
            if m.version in applied:
                if applied[m.version] != m.checksum:
                    raise MigrationChecksumMismatch(m.version)
                continue
            result.append(m)
        return result

    async def apply_all(
        self,
        applied_by: str = "migration-runner",
        preflight: PreflightHook | None = None,
        postflight: PostflightHook | None = None,
    ) -> list[AppliedMigration]:
        applied_migrations: list[AppliedMigration] = []
        for m in await self.pending():
            conn = await self._connect()
            try:
                if preflight is not None and not await preflight(conn, m):
                    async with conn.transaction():
                        await conn.execute(
                            _LEDGER_UPSERT_SQL, m.version, m.description, m.checksum, applied_by, "failed", "skipped"
                        )
                    raise PreflightFailed(m.version)

                postflight_status = "passed"
                async with conn.transaction():
                    await conn.execute(m.sql)
                    if postflight is not None and not await postflight(conn, m):
                        postflight_status = "failed"
                    await conn.execute(
                        _LEDGER_UPSERT_SQL, m.version, m.description, m.checksum, applied_by, "passed", postflight_status
                    )
                if postflight_status == "failed":
                    raise PostflightFailed(m.version)
            finally:
                await conn.close()
            applied_migrations.append(AppliedMigration(m.version, m.description))
        return applied_migrations


async def assert_schema_up_to_date(dsn: str, migrations_dir: Path, expected_version: int) -> int:
    """Startup check (FR-PLT-12 rule 2). Reads only — never applies."""
    runner = MigrationRunner(dsn, migrations_dir)
    actual = await runner.current_version()
    if actual != expected_version:
        raise SchemaVersionMismatch(expected_version, actual)
    return actual
