"""P007 regression (PRD Appendix A: "14 FK violations in a local snapshot"):
an invariant violation a migration assumes away is caught by preflight and
quarantines the migration instead of either silently succeeding or crashing
mid-DDL with a raw Postgres constraint-violation error. This exercises the
generic preflight/postflight hook mechanism (`packages/platform/
migrations_runner.py`, built in 0.B) against a concrete FK-orphan scenario,
per task 0.D ("Тест: инъекция FK/invariant-нарушения → quarantine/read-only,
CI блокирует", `docs/reports/PLAN-MISSION-1.md` §2).

No permanent preflight-check file is added under `migrations/preflight/` —
both README stubs there are explicit that none is needed "until the first
domain migration is written (Phase 1+)"; this test's tmp-path migrations and
inline preflight function are the regression proof for 0.D without
pre-building that Phase 1+ infrastructure ahead of the plan.

FR-PLT-13, P007.
"""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from packages.platform.migrations_runner import Migration, MigrationRunner, PreflightFailed

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"

_NOTIFICATIONS_TABLE = """
CREATE TABLE notifications (
    id BIGSERIAL PRIMARY KEY,
    user_id BIGINT NOT NULL,
    message TEXT NOT NULL
);
"""

_NOTIFICATIONS_FK = """
ALTER TABLE notifications
    ADD CONSTRAINT notifications_user_id_fkey
    FOREIGN KEY (user_id) REFERENCES users (id);
"""


def _base_tmp_migrations(tmp_path: Path) -> Path:
    """Sets up a tmp migrations dir with 0000-0003 (the real ledger/core/jobs
    migrations plus the notifications table, no FK yet). The 0004 FK
    migration is added later by `_add_fk_migration` so the same directory
    can be reused across the test's two stages instead of being recreated."""
    tmp_dir = tmp_path / "migrations"
    tmp_dir.mkdir()
    for name in ("0000_ledger.sql", "0001_platform_core.sql", "0002_platform_jobs.sql"):
        (tmp_dir / name).write_text((MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    (tmp_dir / "0003_notifications.sql").write_text(_NOTIFICATIONS_TABLE, encoding="utf-8")
    return tmp_dir


def _add_fk_migration(tmp_dir: Path) -> Path:
    (tmp_dir / "0004_notifications_fk.sql").write_text(_NOTIFICATIONS_FK, encoding="utf-8")
    return tmp_dir


async def _orphaned_user_id_count(conn: asyncpg.Connection) -> int:
    return await conn.fetchval(
        """
        SELECT count(*) FROM notifications n
        LEFT JOIN users u ON u.id = n.user_id
        WHERE u.id IS NULL
        """
    )


async def _no_orphaned_notifications(conn: asyncpg.Connection, migration: Migration) -> bool:
    if migration.version != 4:
        return True
    return await _orphaned_user_id_count(conn) == 0


async def _fk_constraint_exists(conn: asyncpg.Connection) -> bool:
    return await conn.fetchval("SELECT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'notifications_user_id_fkey')")


async def test_orphaned_fk_rows_block_migration_then_succeed_once_fixed(asyncpg_dsn, tmp_path):
    # Stage 1: legacy data exists with no FK constraint enforcing it yet --
    # exactly the P007 finding: rows already violate a relationship nothing
    # in the schema enforces.
    tmp_dir = _base_tmp_migrations(tmp_path)
    await MigrationRunner(asyncpg_dsn, tmp_dir).apply_all()

    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        await conn.execute("INSERT INTO notifications (user_id, message) VALUES (999999, 'orphaned')")
    finally:
        await conn.close()

    # Stage 2: a later migration tries to add the FK constraint the data is
    # assumed to already satisfy. Preflight catches the violation before the
    # DDL runs at all -- quarantine, not a raw constraint-violation crash
    # partway through a multi-statement migration.
    _add_fk_migration(tmp_dir)
    runner = MigrationRunner(asyncpg_dsn, tmp_dir)

    with pytest.raises(PreflightFailed):
        await runner.apply_all(preflight=_no_orphaned_notifications)

    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        constraint_exists = await _fk_constraint_exists(conn)
        ledger_row = await conn.fetchrow("SELECT preflight_status, postflight_status FROM schema_migrations WHERE version = 4")
    finally:
        await conn.close()

    assert constraint_exists is False
    assert ledger_row["preflight_status"] == "failed"
    assert ledger_row["postflight_status"] == "skipped"
    assert await runner.current_version() == 3

    # Stage 3: quarantine is lifted once the underlying data is fixed (the
    # remediation is an explicit, visible action -- not the migration
    # silently deciding to proceed anyway).
    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        await conn.execute("DELETE FROM notifications WHERE user_id = 999999")
    finally:
        await conn.close()

    applied = await runner.apply_all(preflight=_no_orphaned_notifications)
    assert {m.version for m in applied} == {4}

    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        assert await _fk_constraint_exists(conn) is True
    finally:
        await conn.close()
    assert await runner.current_version() == 4
