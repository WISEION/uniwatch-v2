"""Local-auth session store (Phase 6, task 6.A, D-IDP): a DB-backed session
is required for "correct sign-out" (NFR-SEC-06) to mean something real --
a stateless token can't be revoked before its own expiry, only a
server-side record can. Sessions are revoked, never deleted (same
disable-not-delete discipline `packages/platform/audit.py` already applies
to users) -- a revoked session stays visible to a future audit query.

Session lifetime and lockout policy (5 consecutive failures -> 15 minute
lock) are implementation details recorded in
docs/decisions/OPEN-QUESTIONS.md, not locked PRD numbers."""

from __future__ import annotations

import secrets
from datetime import UTC, datetime, timedelta

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection, AsyncEngine

from packages.platform.auth.models import LoginOutcome
from packages.platform.auth.password_hashing import verify_password
from packages.platform.rbac.models import Identity

SESSION_LIFETIME = timedelta(hours=12)
FAILED_LOGIN_LOCKOUT_THRESHOLD = 5
LOCKOUT_DURATION = timedelta(minutes=15)


async def create_session(conn: AsyncConnection, *, user_id: int) -> str:
    token = secrets.token_urlsafe(32)
    expires_at = datetime.now(UTC) + SESSION_LIFETIME
    await conn.execute(
        text(
            """
            INSERT INTO user_sessions (id, user_id, expires_at)
            VALUES (:id, :user_id, :expires_at)
            """
        ),
        {"id": token, "user_id": user_id, "expires_at": expires_at},
    )
    return token


async def resolve_session(conn: AsyncConnection, token: str) -> Identity | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT u.username, u.status, r.name AS role_name
                    FROM user_sessions s
                    JOIN users u ON u.id = s.user_id
                    JOIN roles r ON r.id = u.role_id
                    WHERE s.id = :token
                      AND s.revoked_at IS NULL
                      AND s.expires_at > now()
                    """
                ),
                {"token": token},
            )
        )
        .mappings()
        .first()
    )
    # Deny-by-default: an unknown/expired/revoked session, or a disabled
    # user whose session outlived their account status, all resolve to no
    # identity -- same posture as rbac/store.py::resolve_identity.
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
    permissions = frozenset(r[0] for r in perm_rows)
    return Identity(subject=row["username"], role=row["role_name"], permissions=permissions)


async def revoke_session(conn: AsyncConnection, token: str) -> None:
    # Idempotent: revoking an already-revoked or unknown token is a no-op,
    # not an error -- sign-out is safe to call more than once.
    await conn.execute(
        text(
            """
            UPDATE user_sessions
            SET revoked_at = now()
            WHERE id = :token AND revoked_at IS NULL
            """
        ),
        {"token": token},
    )


async def record_login_failure(conn: AsyncConnection, *, user_id: int) -> None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    UPDATE users
                    SET failed_login_count = failed_login_count + 1
                    WHERE id = :user_id
                    RETURNING failed_login_count
                    """
                ),
                {"user_id": user_id},
            )
        )
        .mappings()
        .one()
    )
    if row["failed_login_count"] >= FAILED_LOGIN_LOCKOUT_THRESHOLD:
        await conn.execute(
            text("UPDATE users SET locked_until = :locked_until WHERE id = :user_id"),
            {"user_id": user_id, "locked_until": datetime.now(UTC) + LOCKOUT_DURATION},
        )


async def reset_login_failures(conn: AsyncConnection, *, user_id: int) -> None:
    await conn.execute(
        text(
            """
            UPDATE users
            SET failed_login_count = 0, locked_until = NULL
            WHERE id = :user_id
            """
        ),
        {"user_id": user_id},
    )


async def authenticate_user(engine: AsyncEngine, *, username: str, password: str) -> LoginOutcome:
    """The one entry point `POST /auth/login` calls -- combines the
    lockout check, password verification, and session issuance so the
    route itself only maps `LoginOutcome.status` to an HTTP response,
    never re-derives credential/lockout logic at the boundary.

    Takes the engine, not a shared per-request connection: a failed
    attempt's `failed_login_count` increment (and any resulting lockout)
    must survive even though the route handler raises an `ApiError` for
    the 401 response right after this returns -- `apps/api_tender/deps.py`
    `get_connection`'s per-request connection commits on success / rolls
    back on any exception, which would otherwise silently undo the
    increment together with the 401 it caused. Opening its own
    independent transaction here means the bookkeeping commits regardless
    of what the caller does afterward."""
    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        """
                        SELECT u.id, u.username, u.status, u.password_hash, u.locked_until, r.name AS role_name
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
        # Deny-by-default, and deliberately the same outcome for "no such
        # user" and "wrong password" -- a login attempt must not reveal
        # whether a username exists.
        if row is None or row["status"] != "active":
            return LoginOutcome(status="invalid_credentials")

        if row["locked_until"] is not None and row["locked_until"] > datetime.now(UTC):
            return LoginOutcome(status="account_locked")

        if not verify_password(password, row["password_hash"]):
            await record_login_failure(conn, user_id=row["id"])
            return LoginOutcome(status="invalid_credentials")

        await reset_login_failures(conn, user_id=row["id"])

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
        permissions = frozenset(r[0] for r in perm_rows)
        identity = Identity(subject=row["username"], role=row["role_name"], permissions=permissions)
        token = await create_session(conn, user_id=row["id"])
        return LoginOutcome(status="success", identity=identity, session_token=token)
