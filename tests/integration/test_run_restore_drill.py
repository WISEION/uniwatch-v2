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
from unittest.mock import patch
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import text

from packages.platform.restore_drill import latest_passing_drill
from scripts.backup import BackupError
from scripts.run_restore_drill import _redact_dsn_credentials, run_drill


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


async def test_run_drill_records_a_passing_result_in_the_source_database(engine, _database_url, drill_target_dsn, tmp_path: Path):
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
    # I1 (final whole-branch review): the DSN's user:password@ credentials
    # must never be persisted -- only host[:port]/dbname survives.
    assert latest["target_database"] == _redact_dsn_credentials(drill_target_dsn)
    assert "@" not in latest["target_database"]
    assert latest["backup_filename"].startswith("backup_")


async def test_run_drill_records_a_failed_result_when_backup_fails(engine, _database_url, drill_target_dsn, tmp_path: Path):
    """When create_backup() raises BackupError, run_drill() should:
    1. Return exit code 1
    2. Record a passed=False row with the error message as detail
    3. Use a placeholder filename (not a fake real filename)
    """
    backup_error_msg = "pg_dump not found on PATH -- install the PostgreSQL client tools (postgresql-client)"

    with patch("scripts.run_restore_drill.create_backup") as mock_create_backup:
        mock_create_backup.side_effect = BackupError(backup_error_msg)

        exit_code = await run_drill(
            source_database_url=_database_url,
            drill_database_url=drill_target_dsn,
            backup_dir=tmp_path,
        )

    assert exit_code == 1

    # Verify the failure was recorded in the source database
    async with engine.connect() as conn:
        result = await conn.execute(
            text(
                """
                SELECT id, backup_filename, target_database, passed, detail, drilled_at
                FROM restore_drill_runs
                ORDER BY drilled_at DESC, id DESC
                LIMIT 1
                """
            )
        )
        latest = result.mappings().first()

    assert latest is not None
    assert latest["passed"] is False
    assert latest["detail"] == backup_error_msg
    assert latest["target_database"] == _redact_dsn_credentials(drill_target_dsn)
    assert "@" not in latest["target_database"]
    # Placeholder filename when backup fails -- not a fake real filename
    assert latest["backup_filename"] == "(backup failed)"
