"""Server-side permission check for every route/service (FR-ADM-02).
`identity_dependency` is supplied by the caller (`apps/api_tender/deps.py`) — this
module stays agnostic of how identity is authenticated so it does not
depend on any particular IdP (D-IDP is still open)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends

from ..errors import ApiError
from .models import Identity


def require_permission(
    permission: str,
    identity_dependency: Callable[..., Awaitable[Identity]],
) -> Callable[..., Awaitable[Identity]]:
    async def check(identity: Identity = Depends(identity_dependency)) -> Identity:
        if not identity.has_permission(permission):
            raise ApiError(
                status_code=403,
                code="forbidden",
                message=f"missing permission: {permission}",
            )
        return identity

    return check
