"""Disable-not-delete + append-only audit trail (FR-ADM-04, FR-ADM-05, INV-08)."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .correlation import get_correlation_id_or_none


class UserNotFound(Exception):
    def __init__(self, user_id: int):
        super().__init__(f"user {user_id} not found")
        self.user_id = user_id


async def write_audit_log(
    conn: AsyncConnection,
    *,
    actor: str,
    action: str,
    object_type: str,
    object_id: str,
    object_version: int | None,
    reason: str | None,
    correlation_id: str | None = None,
) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO audit_log
                (actor, action, object_type, object_id, object_version, reason, correlation_id)
            VALUES (:actor, :action, :object_type, :object_id, :object_version, :reason, :correlation_id)
            """
        ),
        {
            "actor": actor,
            "action": action,
            "object_type": object_type,
            "object_id": object_id,
            "object_version": object_version,
            "reason": reason,
            "correlation_id": correlation_id or get_correlation_id_or_none() or "unknown",
        },
    )


async def disable_user(conn: AsyncConnection, *, user_id: int, actor: str, reason: str) -> int:
    """Returns the user's new version. No DELETE is ever issued — the row
    and its full audit history stay queryable (INV-08)."""
    row = (
        await conn.execute(text("SELECT version FROM users WHERE id = :id"), {"id": user_id})
    ).mappings().first()
    if row is None:
        raise UserNotFound(user_id)

    new_version = row["version"] + 1
    await conn.execute(
        text(
            """
            UPDATE users
            SET status = 'disabled', version = :new_version, updated_at = now()
            WHERE id = :id
            """
        ),
        {"id": user_id, "new_version": new_version},
    )
    await write_audit_log(
        conn,
        actor=actor,
        action="user.disable",
        object_type="user",
        object_id=str(user_id),
        object_version=new_version,
        reason=reason,
    )
    return new_version
