"""CORS policy on the shared FastAPI bootstrap (packages/platform/app_factory.py).

apps/web is always a different browser origin from apps/api_tender/
apps/api_vendor in this topology -- even docker-compose.local.yml's nginx
serves the built SPA as a pure static file server (apps/web/nginx.conf has
no reverse proxy to the APIs), so a real browser hits this exact
cross-origin path in every environment, not just local dev. Pure ASGI
in-process test, no real DB connection needed -- create_async_engine is
lazy, and /health/live never touches the database.
"""

from __future__ import annotations

import httpx

from packages.platform.app_factory import build_app
from packages.platform.settings import Settings

_FAKE_DSN = "postgresql+asyncpg://fake:fake@127.0.0.1:1/fake"


async def _client(settings: Settings) -> httpx.AsyncClient:
    app = build_app(title="test", routers=[], settings=settings)
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_preflight_from_an_allowed_origin_succeeds():
    settings = Settings(database_url=_FAKE_DSN, cors_allowed_origins=("http://localhost:5173",))
    async with await _client(settings) as client:
        response = await client.options(
            "/health/live",
            headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
        )
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


async def test_preflight_from_a_disallowed_origin_is_not_granted():
    settings = Settings(database_url=_FAKE_DSN, cors_allowed_origins=("http://localhost:5173",))
    async with await _client(settings) as client:
        response = await client.options(
            "/health/live",
            headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "GET"},
        )
    # Starlette's CORSMiddleware still answers the preflight (200), but
    # without an Access-Control-Allow-Origin header for a disallowed
    # origin -- the browser itself is what then refuses to proceed. A
    # wildcard origin would return the header for every request, which is
    # exactly the deny-by-default violation this test guards against.
    assert "access-control-allow-origin" not in response.headers


async def test_actual_response_carries_cors_header_for_an_allowed_origin():
    settings = Settings(database_url=_FAKE_DSN, cors_allowed_origins=("http://localhost:5173",))
    async with await _client(settings) as client:
        response = await client.get("/health/live", headers={"Origin": "http://localhost:5173"})
    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-allow-credentials"] == "true"


async def test_cors_allowed_origins_default_covers_dev_and_compose_ports():
    settings = Settings(database_url=_FAKE_DSN)
    assert settings.cors_allowed_origins == ("http://localhost:5173", "http://localhost:8080")
