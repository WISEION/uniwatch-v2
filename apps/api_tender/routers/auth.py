"""Local-auth login/logout (Phase 6, task 6.A, D-IDP). Replaces the former
dev-only `X-Dev-User` header entirely -- `apps/api_tender/deps.py`'s
`get_current_identity` now resolves from the session cookie this router
issues, not a client-supplied header.

TLS/HTTPS termination is out of scope for this pilot (no reverse proxy
exists yet) -- the session cookie is issued without `Secure` for now, a
recorded gap (`docs/decisions/OPEN-QUESTIONS.md`), not a silent omission.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.auth.session_store import SESSION_LIFETIME, authenticate_user, revoke_session
from packages.platform.errors import ApiError

from ..deps import SESSION_COOKIE_NAME, get_connection

router = APIRouter(prefix="/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    username: str
    role: str


@router.post("/login", response_model=LoginResponse)
async def login(
    body: LoginRequest,
    response: Response,
    request: Request,
) -> LoginResponse:
    # Deliberately not `Depends(get_connection)` -- see authenticate_user's
    # own docstring for why the lockout bookkeeping needs its own
    # independent transaction rather than the per-request connection.
    outcome = await authenticate_user(request.app.state.engine, username=body.username, password=body.password)
    if outcome.status == "account_locked":
        raise ApiError(status_code=401, code="account_locked", message="account is temporarily locked")
    if outcome.status == "invalid_credentials":
        raise ApiError(status_code=401, code="unauthenticated", message="invalid username or password")

    assert outcome.identity is not None and outcome.session_token is not None
    response.set_cookie(
        key=SESSION_COOKIE_NAME,
        value=outcome.session_token,
        httponly=True,
        samesite="lax",
        secure=False,
        max_age=int(SESSION_LIFETIME.total_seconds()),
        path="/",
    )
    return LoginResponse(username=outcome.identity.subject, role=outcome.identity.role)


@router.post("/logout", status_code=204, response_model=None)
async def logout(
    request: Request,
    response: Response,
    conn: AsyncConnection = Depends(get_connection),
) -> None:
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is not None:
        await revoke_session(conn, token)
    response.delete_cookie(key=SESSION_COOKIE_NAME, path="/")
