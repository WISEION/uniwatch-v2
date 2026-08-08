from __future__ import annotations

from collections.abc import AsyncIterator

import httpx
from fastapi import Header, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.errors import ApiError
from packages.platform.rbac.models import Identity
from packages.platform.rbac.store import resolve_identity


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One connection per request, wrapped in a transaction that commits if
    the route returns normally and rolls back on any exception — this is
    what makes idempotency-reserve + mutation + idempotency-store atomic."""
    engine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


async def get_current_identity(
    request: Request,
    x_dev_user: str | None = Header(default=None),
) -> Identity:
    """Dev-only identity resolution (D-IDP — real IdP integration — is
    still an open decision). Deny-by-default: no header, an unknown
    username, or a disabled user are all unauthenticated, never a default
    identity with any access."""
    if x_dev_user is None:
        raise ApiError(status_code=401, code="unauthenticated", message="X-Dev-User header required")

    engine = request.app.state.engine
    async with engine.connect() as conn:
        identity = await resolve_identity(conn, x_dev_user)
    if identity is None:
        raise ApiError(status_code=401, code="unauthenticated", message="unknown or disabled user")
    return identity


async def get_vendor_http_client(request: Request) -> httpx.AsyncClient | None:
    """None in production (packages.contracts.vendor_api.list_vendor_offers
    opens and closes its own client per call, same as every other caller of
    that function) -- overridden in tests via
    app.dependency_overrides[get_vendor_http_client] to point at an
    in-process vendor app through httpx.ASGITransport, exactly like
    tests/contract/test_tender_vendor_contract.py already does for
    list_vendor_offers directly."""
    return getattr(request.app.state, "vendor_http_client", None)
