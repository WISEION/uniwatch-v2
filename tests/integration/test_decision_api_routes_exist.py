"""Smoke check that task 4.A's three routes are registered (task 5 covers
real behavior). Run before Task 4's implementation to confirm the routes
are genuinely missing, and after to confirm they're wired -- this file is
superseded by tests/integration/test_decision_api.py in Task 5 and can be
deleted once that file exists and passes."""

from __future__ import annotations

import httpx

from apps.api_tender.main import create_app
from packages.platform.settings import Settings


async def test_go_no_go_inputs_route_is_registered(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tenders/1/go-no-go-inputs", json={}, headers={"Idempotency-Key": "k1"})
    assert response.status_code != 404


async def test_bid_readiness_candidate_route_is_registered(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tenders/1/bid-readiness-candidate", params={"as_of": "2026-08-08T00:00:00Z"})
    assert response.status_code != 404


async def test_decisions_route_is_registered(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tenders/1/decisions", json={}, headers={"Idempotency-Key": "k1"})
    assert response.status_code != 404
