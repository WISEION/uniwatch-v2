"""Seeds a small, throw-away set of roles/users for `scripts/smoke_test.py`
to log in as against a real, already-running deployment (Phase 6, task 6.B
task 3 -- Gate 5, master plan Section22 Gate 5's "critical route smoke by
role" line).

These are **smoke-testing accounts only** -- never real pilot users. Each
role is granted exactly one permission, on purpose: it lets
`scripts/smoke_test.py` prove both halves of deny-by-default RBAC
(AGENTS.md hard ban #7) against a live server -- "the one route this
identity's permission allows" and "everything else is still denied" -- not
just that the in-process test suite agrees with itself.

Why a seed script rather than asking the operator for existing credentials
(CLAUDE.md's other documented option): a fresh deployment's database has no
users at all, and even an operator's real accounts are unlikely to already
carry this exact one-permission-each split, since real roles are typically
broader. A tiny, clearly-labeled, idempotent seed script is less
speculative than assuming credentials that may not exist.

Idempotent: safe to run more than once against the same database --
roles/permissions/role_permissions are upserted, never duplicated, and the
two users are re-created active with a freshly-hashed password and any
lockout cleared if they already exist (mirrors
`admin_users.py::set_password_route`'s own "reset clears lockout" recovery
discipline).

Usage (after `docker compose -f docker-compose.local.yml up`, or any other
already-migrated deployment reachable at DATABASE_URL):

    python scripts/seed_smoke_test_users.py
    python scripts/smoke_test.py --base-url http://localhost:8001

Do not point this at a real pilot/production database -- it exists only for
smoke/staging deployments where these two throw-away accounts are an
acceptable, disposable presence.
"""

from __future__ import annotations

import asyncio

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.auth.password_hashing import hash_password
from packages.platform.db import get_engine
from packages.platform.settings import get_settings

# Fixed and documented in the open, not secret -- these accounts only ever
# exist to be logged into by scripts/smoke_test.py against a smoke/staging
# deployment. scripts/smoke_test.py's own defaults match these exactly.
SMOKE_TEST_USERS: tuple[dict[str, str], ...] = (
    {
        "role_name": "smoke-test-admin-reader",
        "permission": "admin.users.read",
        "username": "smoke_test_admin_reader",
        "display_name": "Smoke Test (admin reader)",
        "password": "smoke-test-only-admin-reader-9f3a",
    },
    {
        "role_name": "smoke-test-algorithm-reader",
        "permission": "algorithm.policy.read",
        "username": "smoke_test_algorithm_reader",
        "display_name": "Smoke Test (algorithm reader)",
        "password": "smoke-test-only-algorithm-reader-7c2e",
    },
)


async def _upsert_role(conn: AsyncConnection, name: str) -> int:
    row = (await conn.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": name})).first()
    if row is not None:
        return row[0]
    return (await conn.execute(text("INSERT INTO roles (name) VALUES (:name) RETURNING id"), {"name": name})).scalar_one()


async def _upsert_permission(conn: AsyncConnection, name: str) -> int:
    row = (await conn.execute(text("SELECT id FROM permissions WHERE name = :name"), {"name": name})).first()
    if row is not None:
        return row[0]
    return (await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": name})).scalar_one()


async def _ensure_role_permission(conn: AsyncConnection, role_id: int, permission_id: int) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO role_permissions (role_id, permission_id)
            VALUES (:role_id, :permission_id)
            ON CONFLICT (role_id, permission_id) DO NOTHING
            """
        ),
        {"role_id": role_id, "permission_id": permission_id},
    )


async def _upsert_user(conn: AsyncConnection, *, username: str, display_name: str, role_id: int, password: str) -> None:
    # Same recovery shape as admin_users.py::set_password_route: rewriting
    # the password also clears any lockout and forces status back to
    # active, so re-running this script always leaves a usable account
    # rather than one still locked out from a previous smoke run.
    await conn.execute(
        text(
            """
            INSERT INTO users (username, display_name, role_id, password_hash)
            VALUES (:username, :display_name, :role_id, :password_hash)
            ON CONFLICT (username) DO UPDATE
            SET display_name = EXCLUDED.display_name,
                role_id = EXCLUDED.role_id,
                password_hash = EXCLUDED.password_hash,
                status = 'active',
                failed_login_count = 0,
                locked_until = NULL,
                version = users.version + 1,
                updated_at = now()
            """
        ),
        {
            "username": username,
            "display_name": display_name,
            "role_id": role_id,
            "password_hash": hash_password(password),
        },
    )


async def main() -> None:
    settings = get_settings()
    engine = get_engine(settings.database_url)
    try:
        async with engine.begin() as conn:
            for spec in SMOKE_TEST_USERS:
                role_id = await _upsert_role(conn, spec["role_name"])
                permission_id = await _upsert_permission(conn, spec["permission"])
                await _ensure_role_permission(conn, role_id, permission_id)
                await _upsert_user(
                    conn,
                    username=spec["username"],
                    display_name=spec["display_name"],
                    role_id=role_id,
                    password=spec["password"],
                )
    finally:
        await engine.dispose()

    print("seeded smoke-test users:")
    for spec in SMOKE_TEST_USERS:
        print(f"  {spec['username']} / {spec['password']}  (role={spec['role_name']}, permission={spec['permission']})")


if __name__ == "__main__":
    asyncio.run(main())
