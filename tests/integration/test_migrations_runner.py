"""FR-PLT-12, DM-06, P007, P114."""

from __future__ import annotations

from pathlib import Path

import asyncpg
import pytest

from packages.platform.migrations_runner import (
    MigrationChecksumMismatch,
    MigrationRunner,
    PostflightFailed,
    PreflightFailed,
    SchemaVersionMismatch,
    assert_schema_up_to_date,
)

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


async def test_apply_all_on_empty_db_applies_every_migration(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    applied = await runner.apply_all()
    versions = {m.version for m in applied}
    assert versions == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}
    assert await runner.current_version() == 13


async def test_apply_all_is_idempotent_on_already_migrated_db(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    await runner.apply_all()
    second_run = await runner.apply_all()
    assert second_run == []
    assert await runner.current_version() == 13


async def test_apply_all_on_seeded_db_only_applies_pending(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        await conn.execute((MIGRATIONS_DIR / "0000_ledger.sql").read_text(encoding="utf-8"))
        await conn.execute((MIGRATIONS_DIR / "0001_platform_core.sql").read_text(encoding="utf-8"))
        checksum = next(m.checksum for m in runner.discover() if m.version == 1)
        await conn.execute(
            """
            INSERT INTO schema_migrations (version, description, checksum, applied_by, preflight_status, postflight_status)
            VALUES (1, 'platform core', $1, 'seed', 'passed', 'passed')
            """,
            checksum,
        )
    finally:
        await conn.close()

    applied = await runner.apply_all()
    assert {m.version for m in applied} == {2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13}


async def test_edited_migration_after_apply_raises_checksum_mismatch(asyncpg_dsn, tmp_path):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    await runner.apply_all()

    tampered_dir = tmp_path / "migrations"
    tampered_dir.mkdir()
    for name in ("0000_ledger.sql", "0001_platform_core.sql", "0002_platform_jobs.sql"):
        (tampered_dir / name).write_text((MIGRATIONS_DIR / name).read_text(encoding="utf-8"), encoding="utf-8")
    tampered = tampered_dir / "0001_platform_core.sql"
    tampered.write_text(tampered.read_text(encoding="utf-8") + "\n-- tampered\n", encoding="utf-8")

    tampered_runner = MigrationRunner(asyncpg_dsn, tampered_dir)
    with pytest.raises(MigrationChecksumMismatch):
        await tampered_runner.apply_all()


async def test_preflight_failure_blocks_ddl_and_is_recorded(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)

    async def failing_preflight(conn, migration):
        return migration.version != 1

    with pytest.raises(PreflightFailed):
        await runner.apply_all(preflight=failing_preflight)

    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.users') IS NOT NULL")
        row = await conn.fetchrow("SELECT preflight_status, postflight_status FROM schema_migrations WHERE version = 1")
    finally:
        await conn.close()
    assert exists is False
    assert row["preflight_status"] == "failed"
    assert row["postflight_status"] == "skipped"


async def test_postflight_failure_commits_ddl_but_not_current_version(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)

    async def failing_postflight(conn, migration):
        return migration.version != 1

    with pytest.raises(PostflightFailed):
        await runner.apply_all(postflight=failing_postflight)

    conn = await asyncpg.connect(asyncpg_dsn)
    try:
        exists = await conn.fetchval("SELECT to_regclass('public.users') IS NOT NULL")
    finally:
        await conn.close()
    assert exists is True
    # version 1's postflight failed so it is excluded; only the bootstrap
    # ledger row (version 0) remains "current".
    assert await runner.current_version() == 0


async def test_startup_check_raises_on_version_mismatch(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    await runner.apply_all()
    with pytest.raises(SchemaVersionMismatch):
        await assert_schema_up_to_date(asyncpg_dsn, MIGRATIONS_DIR, expected_version=99)


async def test_startup_check_passes_when_versions_match(asyncpg_dsn):
    runner = MigrationRunner(asyncpg_dsn, MIGRATIONS_DIR)
    await runner.apply_all()
    version = await assert_schema_up_to_date(asyncpg_dsn, MIGRATIONS_DIR, expected_version=13)
    assert version == 13
