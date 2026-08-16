"""Backup/restore drill (Phase 6 task 6.B Task 1, `NFR-REL-01`, master plan
§22 Gate 3's "backup/restore drill status" -- `docs/operations/cutover-plan.md`
§2 criterion 2: "a real backup restore ... has been performed and its result
logged, not merely scheduled"). This test's pass/fail *is* that evidence.

It is deliberately not a smoke test of "the scripts run" -- it seeds real
rows into a migrated database spanning packages/platform (RBAC),
packages/algorithm (policy graph), and packages/tender (raw evidence),
backs that database up via `scripts/backup.py`'s real `pg_dump` subprocess
call, restores the resulting dump via `scripts/restore.py`'s real
`pg_restore` subprocess call into a SECOND, wholly separate, empty database
on the same testcontainers Postgres instance, and asserts every seeded row
comes back byte-for-byte identical. A restore into the same database/schema
the backup came from would not prove anything -- the point of a restore
drill is recovering into a target that never had the data any other way.
"""

from __future__ import annotations

import json
import uuid
from urllib.parse import urlsplit, urlunsplit

import asyncpg
import pytest_asyncio
from sqlalchemy import text

from packages.platform.auth.password_hashing import hash_password
from packages.platform.db import get_engine
from scripts.backup import create_backup
from scripts.restore import restore_backup

TEST_PASSWORD = "drill-password-123"


def _dsn_with_dbname(dsn: str, dbname: str) -> str:
    parts = urlsplit(dsn)
    return urlunsplit((parts.scheme, parts.netloc, f"/{dbname}", parts.query, parts.fragment))


@pytest_asyncio.fixture
async def restore_target_dsn(_asyncpg_base_dsn):
    """A second, empty database on the same running Postgres container --
    created fresh here (not via `MigrationRunner`, since the whole point of
    the drill is that `pg_restore` alone recreates the schema from the
    dump), and dropped again afterward so one-off drill databases don't
    accumulate across a test session."""
    db_name = f"restore_drill_{uuid.uuid4().hex[:12]}"
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


async def _seed_source_rows(engine) -> dict[str, int]:
    """Real rows in a representative slice of already-migrated tables --
    RBAC (roles/permissions/role_permissions/users), the policy-graph
    domain (policy_graphs), and raw tender evidence (raw_snapshots) --
    exactly the kind of heterogeneous data an actual production backup
    would contain."""
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('drill-admin') RETURNING id"))).scalar()
        permission_id = (
            await conn.execute(text("INSERT INTO permissions (name) VALUES ('drill.permission') RETURNING id"))
        ).scalar()
        await conn.execute(
            text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
            {"r": role_id, "p": permission_id},
        )
        user_id = (
            await conn.execute(
                text(
                    "INSERT INTO users (username, display_name, role_id, password_hash) "
                    "VALUES ('drill-user', 'Drill User', :r, :ph) RETURNING id"
                ),
                {"r": role_id, "ph": hash_password(TEST_PASSWORD)},
            )
        ).scalar()
        policy_graph_id = (
            await conn.execute(
                text(
                    "INSERT INTO policy_graphs (name, description, owner) "
                    "VALUES ('Drill Policy', 'seeded by test_restore_drill', 'drill-owner') RETURNING id"
                )
            )
        ).scalar()
        raw_snapshot_id = (
            await conn.execute(
                text(
                    "INSERT INTO raw_snapshots "
                    "(source, resource_type, identity_key, checksum, body, contract_version, correlation_id) "
                    "VALUES ('drill-source', 'drill-resource', 'drill-identity-1', 'deadbeef', "
                    "CAST(:body AS JSONB), 'v1', 'drill-correlation-1') RETURNING id"
                ),
                {"body": json.dumps({"seeded": True, "n": 42})},
            )
        ).scalar()

    return {
        "role_id": role_id,
        "permission_id": permission_id,
        "user_id": user_id,
        "policy_graph_id": policy_graph_id,
        "raw_snapshot_id": raw_snapshot_id,
    }


async def _fetch_row(engine, table: str, row_id: int) -> dict:
    async with engine.begin() as conn:
        row = (await conn.execute(text(f"SELECT * FROM {table} WHERE id = :id"), {"id": row_id})).mappings().first()
    assert row is not None, f"expected row id={row_id} in {table}"
    return dict(row)


async def _fetch_role_permission(engine, role_id: int, permission_id: int) -> dict:
    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT * FROM role_permissions WHERE role_id = :r AND permission_id = :p"),
                    {"r": role_id, "p": permission_id},
                )
            )
            .mappings()
            .first()
        )
    assert row is not None, f"expected role_permissions row ({role_id}, {permission_id})"
    return dict(row)


async def _snapshot(engine, seeded: dict[str, int]) -> dict:
    return {
        "roles": await _fetch_row(engine, "roles", seeded["role_id"]),
        "permissions": await _fetch_row(engine, "permissions", seeded["permission_id"]),
        "role_permissions": await _fetch_role_permission(engine, seeded["role_id"], seeded["permission_id"]),
        "users": await _fetch_row(engine, "users", seeded["user_id"]),
        "policy_graphs": await _fetch_row(engine, "policy_graphs", seeded["policy_graph_id"]),
        "raw_snapshots": await _fetch_row(engine, "raw_snapshots", seeded["raw_snapshot_id"]),
    }


async def test_restore_drill_recovers_seeded_rows_exactly(engine, _database_url, restore_target_dsn, tmp_path):
    seeded = await _seed_source_rows(engine)

    # Snapshot every seeded row from the SOURCE database before backing up,
    # so the later comparison is against what was actually written, not an
    # assumption about it.
    before = await _snapshot(engine, seeded)

    # 1. Real backup, via scripts/backup.py's actual pg_dump subprocess call.
    backup_path = create_backup(_database_url, tmp_path / "backups")
    assert backup_path.exists()
    assert backup_path.stat().st_size > 0

    # 2. Real restore, via scripts/restore.py's actual pg_restore subprocess
    #    call, into a SECOND, wholly separate, empty database that never had
    #    this data any other way (no migrations applied to it -- pg_restore
    #    alone recreates the schema from the dump).
    restore_backup(backup_path, restore_target_dsn)

    # 3. Assert the restored database's rows match the original EXACTLY.
    restored_engine = get_engine(restore_target_dsn.replace("postgresql://", "postgresql+asyncpg://", 1))
    try:
        after = await _snapshot(restored_engine, seeded)
    finally:
        await restored_engine.dispose()

    assert after == before
