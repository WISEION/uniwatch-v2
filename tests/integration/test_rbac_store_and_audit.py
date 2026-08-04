"""FR-ADM-01, FR-ADM-04, FR-ADM-05, INV-08."""

from __future__ import annotations

from sqlalchemy import text

from packages.platform.audit import UserNotFound, disable_user
from packages.platform.rbac.store import resolve_identity


async def _seed_role(conn, name: str) -> int:
    row = (await conn.execute(text("INSERT INTO roles (name) VALUES (:name) RETURNING id"), {"name": name})).first()
    return row[0]


async def _seed_permission(conn, name: str) -> int:
    row = (await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": name})).first()
    return row[0]


async def _seed_user(conn, username: str, role_id: int, status: str = "active") -> int:
    row = (
        await conn.execute(
            text(
                """
                INSERT INTO users (username, display_name, role_id, status)
                VALUES (:username, :username, :role_id, :status)
                RETURNING id
                """
            ),
            {"username": username, "role_id": role_id, "status": status},
        )
    ).first()
    return row[0]


async def test_role_with_no_permission_rows_resolves_to_empty_set(engine):
    async with engine.begin() as conn:
        role_id = await _seed_role(conn, "empty_role")
        await _seed_user(conn, "empty-user", role_id)

    async with engine.begin() as conn:
        identity = await resolve_identity(conn, "empty-user")
    assert identity is not None
    assert identity.permissions == frozenset()


async def test_role_with_granted_permission_resolves_it(engine):
    async with engine.begin() as conn:
        role_id = await _seed_role(conn, "analyst")
        permission_id = await _seed_permission(conn, "widgets.read")
        await conn.execute(
            text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
            {"r": role_id, "p": permission_id},
        )
        await _seed_user(conn, "analyst-user", role_id)

    async with engine.begin() as conn:
        identity = await resolve_identity(conn, "analyst-user")
    assert identity.permissions == frozenset({"widgets.read"})


async def test_unknown_username_resolves_to_none(engine):
    async with engine.begin() as conn:
        identity = await resolve_identity(conn, "does-not-exist")
    assert identity is None


async def test_disabled_user_resolves_to_none(engine):
    async with engine.begin() as conn:
        role_id = await _seed_role(conn, "role_x")
        await _seed_user(conn, "disabled-user", role_id, status="disabled")

    async with engine.begin() as conn:
        identity = await resolve_identity(conn, "disabled-user")
    assert identity is None


async def test_disable_user_keeps_row_and_writes_audit_not_delete(engine):
    async with engine.begin() as conn:
        role_id = await _seed_role(conn, "role_y")
        user_id = await _seed_user(conn, "to-disable", role_id)

    async with engine.begin() as conn:
        new_version = await disable_user(conn, user_id=user_id, actor="admin-1", reason="offboarding")
        assert new_version == 2

    async with engine.begin() as conn:
        row = (await conn.execute(text("SELECT status, version FROM users WHERE id = :id"), {"id": user_id})).mappings().first()
        assert row["status"] == "disabled"
        assert row["version"] == 2

        audit_row = (
            (
                await conn.execute(
                    text("SELECT actor, action, object_type, object_id, reason FROM audit_log WHERE object_id = :id"),
                    {"id": str(user_id)},
                )
            )
            .mappings()
            .first()
        )
        assert audit_row["actor"] == "admin-1"
        assert audit_row["action"] == "user.disable"
        assert audit_row["object_type"] == "user"
        assert audit_row["reason"] == "offboarding"


async def test_disable_unknown_user_raises(engine):
    async with engine.begin() as conn:
        try:
            await disable_user(conn, user_id=999999, actor="admin-1", reason="n/a")
            raised = False
        except UserNotFound:
            raised = True
    assert raised
