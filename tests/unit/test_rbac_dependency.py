"""FR-ADM-01, FR-ADM-02, INV-08."""

from __future__ import annotations

import httpx
from fastapi import Depends, FastAPI

from packages.platform.correlation import CorrelationIdMiddleware
from packages.platform.errors import install_error_handlers
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity


def make_app(identity: Identity) -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)

    async def fake_identity_dependency() -> Identity:
        return identity

    @app.get("/protected")
    async def protected(
        current: Identity = Depends(require_permission("widgets.read", fake_identity_dependency)),
    ):
        return {"subject": current.subject}

    return app


async def _get(identity: Identity):
    app = make_app(identity)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        return await client.get("/protected")


async def test_identity_with_permission_is_allowed():
    identity = Identity(subject="alice", role="analyst", permissions=frozenset({"widgets.read"}))
    response = await _get(identity)
    assert response.status_code == 200
    assert response.json() == {"subject": "alice"}


async def test_identity_without_permission_is_denied_403():
    identity = Identity(subject="bob", role="viewer", permissions=frozenset())
    response = await _get(identity)
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_unknown_role_with_no_permission_rows_denies_by_default():
    # A role that exists but has zero role_permissions rows resolves to an
    # empty permission set upstream (packages/platform/rbac/store.py) — the
    # dependency itself just has to deny that empty set, same as any other.
    identity = Identity(subject="new-role-user", role="freshly_created_role", permissions=frozenset())
    response = await _get(identity)
    assert response.status_code == 403
