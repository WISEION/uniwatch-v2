"""Platform admin/users: the one concrete resource in this skeleton,
demonstrating idempotency (FR-PLT-03), cursor pagination (FR-PLT-05), ETag
precondition (FR-PLT-04), RBAC deny-by-default (FR-ADM-01/02), and
disable-not-delete + audit (FR-ADM-04/05) end to end over real HTTP.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.audit import UserNotFound, disable_user, write_audit_log
from packages.platform.auth.password_hashing import hash_password
from packages.platform.concurrency import check_precondition
from packages.platform.errors import ApiError
from packages.platform.idempotency import IdempotencyKeyReused, IdempotencyStore, fingerprint
from packages.platform.pagination import decode_cursor, encode_cursor
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity

from ..deps import get_connection, get_current_identity

router = APIRouter(prefix="/admin/users", tags=["admin-users"])

_idempotency_store = IdempotencyStore()


class CreateUserRequest(BaseModel):
    username: str
    display_name: str
    role_name: str


class UpdateUserRequest(BaseModel):
    display_name: str | None = None
    role_name: str | None = None


class DisableUserRequest(BaseModel):
    reason: str


class SetPasswordRequest(BaseModel):
    password: str


class UserResponse(BaseModel):
    id: int
    username: str
    display_name: str
    role_name: str
    status: str
    version: int


class UserListResponse(BaseModel):
    items: list[UserResponse]
    next_cursor: str | None


async def _load_role_id(conn: AsyncConnection, role_name: str) -> int:
    row = (await conn.execute(text("SELECT id FROM roles WHERE name = :name"), {"name": role_name})).first()
    if row is None:
        raise ApiError(status_code=422, code="unknown_role", message=f"unknown role: {role_name}")
    return row[0]


async def _load_user_row(conn: AsyncConnection, user_id: int) -> dict:
    row = (
        (
            await conn.execute(
                text(
                    """
                SELECT u.id, u.username, u.display_name, u.status, u.version, r.name AS role_name
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id = :id
                """
                ),
                {"id": user_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ApiError(status_code=404, code="not_found", message=f"user {user_id} not found")
    return dict(row)


@router.post("", response_model=UserResponse, status_code=201)
async def create_user(
    body: CreateUserRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("admin.users.create", get_current_identity)),
) -> UserResponse:
    route = "POST /admin/users"
    request_fingerprint = fingerprint(body.model_dump())
    try:
        existing = await _idempotency_store.reserve(conn, idempotency_key, route, request_fingerprint)
    except IdempotencyKeyReused as exc:
        raise ApiError(status_code=409, code="idempotency_key_reused", message=str(exc)) from exc
    if existing is not None:
        return UserResponse(**existing.response_body)

    role_id = await _load_role_id(conn, body.role_name)
    row = (
        (
            await conn.execute(
                text(
                    """
                INSERT INTO users (username, display_name, role_id)
                VALUES (:username, :display_name, :role_id)
                RETURNING id, version, status
                """
                ),
                {"username": body.username, "display_name": body.display_name, "role_id": role_id},
            )
        )
        .mappings()
        .one()
    )

    response = UserResponse(
        id=row["id"],
        username=body.username,
        display_name=body.display_name,
        role_name=body.role_name,
        status=row["status"],
        version=row["version"],
    )
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="user.create",
        object_type="user",
        object_id=str(row["id"]),
        object_version=row["version"],
        reason=None,
    )
    await _idempotency_store.store_response(conn, idempotency_key, route, 201, response.model_dump())
    return response


@router.get("", response_model=UserListResponse)
async def list_users(
    cursor: str | None = None,
    limit: int = 20,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("admin.users.read", get_current_identity)),
) -> UserListResponse:
    after_id = decode_cursor(cursor)[0] if cursor else 0
    rows = (
        (
            await conn.execute(
                text(
                    """
                SELECT u.id, u.username, u.display_name, u.status, u.version, r.name AS role_name
                FROM users u
                JOIN roles r ON r.id = u.role_id
                WHERE u.id > :after_id
                ORDER BY u.id ASC
                LIMIT :limit_plus_one
                """
                ),
                {"after_id": after_id, "limit_plus_one": limit + 1},
            )
        )
        .mappings()
        .all()
    )

    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor((page[-1]["id"],)) if has_more else None
    return UserListResponse(
        items=[UserResponse(**dict(row)) for row in page],
        next_cursor=next_cursor,
    )


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    body: UpdateUserRequest,
    if_match: str = Header(..., alias="If-Match"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("admin.users.update", get_current_identity)),
) -> UserResponse:
    current = await _load_user_row(conn, user_id)
    check_precondition(if_match, current["version"])

    display_name = body.display_name if body.display_name is not None else current["display_name"]
    role_name = body.role_name if body.role_name is not None else current["role_name"]
    role_id = await _load_role_id(conn, role_name)

    row = (
        (
            await conn.execute(
                text(
                    """
                UPDATE users
                SET display_name = :display_name, role_id = :role_id,
                    version = version + 1, updated_at = now()
                WHERE id = :id
                RETURNING version, status
                """
                ),
                {"display_name": display_name, "role_id": role_id, "id": user_id},
            )
        )
        .mappings()
        .one()
    )

    await write_audit_log(
        conn,
        actor=identity.subject,
        action="user.update",
        object_type="user",
        object_id=str(user_id),
        object_version=row["version"],
        reason=None,
    )
    return UserResponse(
        id=user_id,
        username=current["username"],
        display_name=display_name,
        role_name=role_name,
        status=row["status"],
        version=row["version"],
    )


@router.post("/{user_id}/disable", response_model=UserResponse)
async def disable_user_route(
    user_id: int,
    body: DisableUserRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("admin.users.disable", get_current_identity)),
) -> UserResponse:
    try:
        await disable_user(conn, user_id=user_id, actor=identity.subject, reason=body.reason)
    except UserNotFound as exc:
        raise ApiError(status_code=404, code="not_found", message=str(exc)) from exc
    return UserResponse(**await _load_user_row(conn, user_id))


@router.post("/{user_id}/set-password", status_code=204, response_model=None)
async def set_password_route(
    user_id: int,
    body: SetPasswordRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("admin.users.set_password", get_current_identity)),
) -> None:
    # A password is set as a distinct, explicit step -- never as part of
    # user creation -- same "capability separate from creation" shape as
    # disable-not-delete. Also clears any existing lockout: an admin
    # resetting a locked-out user's password is the recovery path.
    await _load_user_row(conn, user_id)  # 404s if the user doesn't exist
    await conn.execute(
        text(
            """
            UPDATE users
            SET password_hash = :password_hash, failed_login_count = 0, locked_until = NULL,
                version = version + 1, updated_at = now()
            WHERE id = :id
            """
        ),
        {"password_hash": hash_password(body.password), "id": user_id},
    )
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="user.set_password",
        object_type="user",
        object_id=str(user_id),
        object_version=None,
        reason=None,
    )
