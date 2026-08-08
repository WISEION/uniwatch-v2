"""NFR-OBS-01, NFR-OBS-03, FR-PLT-12."""

from __future__ import annotations

import httpx
import pytest_asyncio

from apps.api_tender.main import create_app
from packages.platform.settings import Settings


@pytest_asyncio.fixture
async def client(engine, _database_url, migrated_asyncpg_dsn):
    settings = Settings(database_url=_database_url, expected_schema_version=13)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
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
    assert body["schema_version"] == 13


async def test_readiness_fails_on_schema_mismatch(engine, _database_url, migrated_asyncpg_dsn):
    settings = Settings(database_url=_database_url, expected_schema_version=99)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/health/ready")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "not_ready"
