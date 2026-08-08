"""Smoke check that task 4.A's three routes are registered (task 5 covers
real behavior). Run before Task 4's implementation to confirm the routes
are genuinely missing, and after to confirm they're wired -- this file is
superseded by tests/integration/test_decision_api.py in Task 5 and can be
deleted once that file exists and passes.

Also covers three review-flagged 500-vs-4xx regressions (task 4.A review
fix): a naive `as_of` on the bid-readiness route, and a nonexistent
`tender_id` on both POST routes must all get a clean 4xx, never an
unhandled 500 from a raw TypeError/IntegrityError."""

from __future__ import annotations

import httpx
from sqlalchemy import text

from apps.api_tender.main import create_app
from packages.platform.settings import Settings


async def _seed_user_with_permission(engine, *, username: str, permission: str) -> None:
    """Minimal RBAC seed (mirrors tests/integration/test_admin_users_api.py's
    admin_user fixture pattern) so a route's real 4xx-vs-500 behavior can be
    exercised past the identity/permission dependency, not just probed for
    a 401 short-circuit."""
    async with engine.begin() as conn:
        role_id = (
            await conn.execute(text("INSERT INTO roles (name) VALUES (:name) RETURNING id"), {"name": f"role-{username}"})
        ).scalar()
        permission_id = (
            await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": permission})
        ).scalar()
        await conn.execute(
            text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
            {"r": role_id, "p": permission_id},
        )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES (:u, :u, :r)"),
            {"u": username, "r": role_id},
        )


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


async def test_bid_readiness_candidate_rejects_naive_as_of(engine, _database_url):
    await _seed_user_with_permission(engine, username="reader-1", permission="decision.bid_readiness.read")
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get(
            "/tenders/1/bid-readiness-candidate",
            params={"as_of": "2026-08-08T00:00:00"},
            headers={"X-Dev-User": "reader-1"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "naive_datetime"


async def test_go_no_go_inputs_with_nonexistent_tender_returns_422(engine, _database_url):
    await _seed_user_with_permission(engine, username="creator-1", permission="decision.go_no_go.create")
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/tenders/999999999/go-no-go-inputs",
            json={
                "company_profile_notes": "x",
                "qualification_notes": "x",
                "financing_notes": "x",
                "customer_reputation_notes": "x",
                "pre_designated_winner_suspected": False,
            },
            headers={"Idempotency-Key": "k-nonexistent-1", "X-Dev-User": "creator-1"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"


async def test_decisions_with_nonexistent_tender_returns_422(engine, _database_url):
    await _seed_user_with_permission(engine, username="decider-1", permission="decision.decisions.create")
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/tenders/999999999/decisions",
            json={"decision_type": "go", "conditions": [], "justification": "x"},
            headers={"Idempotency-Key": "k-nonexistent-2", "X-Dev-User": "decider-1"},
        )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"
