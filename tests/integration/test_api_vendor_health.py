"""NFR-OBS-01, NFR-OBS-03, FR-PLT-12 -- apps/api_vendor's own health check,
independent of apps/api_tender (ADR-0006: separate deployable services)."""

from __future__ import annotations

import httpx
import pytest_asyncio

from apps.api_vendor.main import create_app
from packages.platform.settings import Settings


@pytest_asyncio.fixture
async def client(engine, _database_url, migrated_asyncpg_dsn):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as c:
        yield c


async def test_liveness_is_always_ok(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok_when_schema_matches(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == 22


async def test_internal_ping_is_unauthenticated_and_static(client):
    # Deliberately unauthenticated (ADR-0006 defers real service-to-service
    # auth to D-IDP/D-HOST) and deliberately static, not real vendor data
    # (packages/vendor has no domain code yet) -- this endpoint exists only
    # to prove the tender<->vendor API contract mechanism.
    response = await client.get("/internal/ping")
    assert response.status_code == 200
    assert response.json() == {"service": "vendor", "status": "ok"}
