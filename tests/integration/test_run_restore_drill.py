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
    assert latest["target_database"] == drill_target_dsn
    assert latest["backup_filename"].startswith("backup_")
