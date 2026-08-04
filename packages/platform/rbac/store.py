"""Deny-by-default identity/permission resolution (FR-ADM-01, INV-08).

An unknown username, or a `disabled` user, resolves to `None` (no
identity) rather than an identity with an empty permission set — both are
denied by `require_permission`, but keeping the distinction lets callers
tell "not authenticated" (401) apart from "authenticated, missing
permission" (403).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .models import Identity


async def resolve_identity(conn: AsyncConnection, username: str) -> Identity | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                SELECT u.status, r.name AS role_name
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.username = :username
                """
                ),
                {"username": username},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["status"] != "active":
        return None

    perm_rows = await conn.execute(
        text(
            """
            SELECT p.name
            FROM role_permissions rp
            JOIN permissions p ON p.id = rp.permission_id
            JOIN roles r ON r.id = rp.role_id
            WHERE r.name = :role_name
            """
        ),
        {"role_name": row["role_name"]},
    )
    # A role with no role_permissions rows resolves to an empty set — the
    # deny-by-default default, not an error.
    permissions = frozenset(r[0] for r in perm_rows)
    return Identity(subject=username, role=row["role_name"], permissions=permissions)
