"""Seeds Phase 6 task 6.D's real pilot roles/permission matrix and the
initial set of pilot user accounts (D-PILOT, `docs/reports/PLAN-MISSION-6.md`
Section3 task 6.D -- "pilot users and their exact permission matrix").

D-PILOT's decision, given by the owner in chat 2026-08-17 (recorded in
`docs/decisions/OPEN-QUESTIONS.md`): 12 pilot users across 4 roles --
6 `worker`, 2 `tender`, 2 `procurement`, 2 `technical_specialist` -- with
the permission matrix below. This is real operational data, not a
smoke-test throwaway set (contrast `scripts/seed_smoke_test_users.py`,
which is exactly that): passwords are generated fresh per run with
`secrets.token_urlsafe`, never hardcoded in this file, and printed to
stdout exactly once so the operator can hand them to the real person each
placeholder username stands in for, then rename the account (`PATCH
/admin/users/{id}` -- `display_name` at least; renaming `username` itself
is not supported by that endpoint today) once real identities are known.

Idempotent for roles/permissions/role_permissions (safe to re-run to add a
missing permission later). NOT idempotent for users past their first
creation -- a user row that already exists is left untouched (role
included), so re-running this script can never silently reset or
re-permission an already-distributed real credential. To change an
existing pilot user's role, use `PATCH /admin/users/{id}` (`admin.users.update`)
instead of re-running this script.

Usage (against an already-migrated deployment reachable at DATABASE_URL):

    python scripts/seed_pilot_users.py
"""

from __future__ import annotations

import asyncio
import secrets

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.auth.password_hashing import hash_password
from packages.platform.db import get_engine
from packages.platform.settings import get_settings

# The permission matrix itself -- D-PILOT's decision, not an invented
# default: worker (operational, read-heavy + logs execution facts), tender
# (drives bid/no-bid decisions and forecasting), procurement (owns
# post-decision outcomes/execution close-out), technical_specialist (owns
# the policy graph/АЛГОРИТМ config and user administration).
PILOT_ROLES: dict[str, tuple[str, ...]] = {
    "worker": (
        "decision.bid_readiness.read",
        "decision.recalc_flags.read",
        "decision.execution_facts.read",
        "decision.execution_facts.create",
        "tender.forecast_snapshot.read",
        "platform.feedback.submit",
    ),
    "tender": (
        "decision.bid_readiness.read",
        "decision.recalc_flags.read",
        "decision.decisions.create",
        "decision.go_no_go.create",
        "tender.forecast_snapshot.read",
        "tender.forecast_snapshot.write",
        "platform.feedback.submit",
    ),
    "procurement": (
        "decision.execution_facts.read",
        "decision.execution_facts.create",
        "decision.execution_facts.close_project",
        "decision.outcome.read",
        "decision.outcome.write",
        "platform.feedback.submit",
    ),
    "technical_specialist": (
        "algorithm.policy.read",
        "algorithm.policy.write",
        "algorithm.policy.approve",
        "algorithm.policy.activate",
        "algorithm.simulation.read",
        "algorithm.simulation.write",
        "admin.users.create",
        "admin.users.read",
        "admin.users.update",
        "admin.users.disable",
        "admin.users.set_password",
        "platform.feedback.submit",
        "platform.feedback.triage",
    ),
}

# Headcount per role, per D-PILOT's decision -- 12 pilot users total.
# Usernames are placeholders (pilot_<role>_<n>) since no real names were
# given; rename via display_name once real identities are assigned.
PILOT_HEADCOUNT: dict[str, int] = {
    "worker": 6,
    "tender": 2,
    "procurement": 2,
    "technical_specialist": 2,
}


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


async def _user_exists(conn: AsyncConnection, username: str) -> bool:
    row = (await conn.execute(text("SELECT 1 FROM users WHERE username = :username"), {"username": username})).first()
    return row is not None


async def _create_user(conn: AsyncConnection, *, username: str, display_name: str, role_id: int, password: str) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO users (username, display_name, role_id, password_hash)
            VALUES (:username, :display_name, :role_id, :password_hash)
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
    created: list[tuple[str, str]] = []
    skipped: list[str] = []
    try:
        async with engine.begin() as conn:
            role_ids: dict[str, int] = {}
            for role_name, permissions in PILOT_ROLES.items():
                role_id = await _upsert_role(conn, role_name)
                role_ids[role_name] = role_id
                for permission_name in permissions:
                    permission_id = await _upsert_permission(conn, permission_name)
                    await _ensure_role_permission(conn, role_id, permission_id)

            for role_name, headcount in PILOT_HEADCOUNT.items():
                for n in range(1, headcount + 1):
                    username = f"pilot_{role_name}_{n}"
                    if await _user_exists(conn, username):
                        skipped.append(username)
                        continue
                    password = secrets.token_urlsafe(16)
                    await _create_user(
                        conn,
                        username=username,
                        display_name=f"Pilot {role_name} #{n} (placeholder -- rename once assigned)",
                        role_id=role_ids[role_name],
                        password=password,
                    )
                    created.append((username, password))
    finally:
        await engine.dispose()

    if created:
        print("created pilot users (record these now -- shown only this once):")
        for username, password in created:
            print(f"  {username} / {password}")
    if skipped:
        print("already existed, left untouched:")
        for username in skipped:
            print(f"  {username}")


if __name__ == "__main__":
    asyncio.run(main())
