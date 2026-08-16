"""Local-auth account lockout (Phase 6, task 6.A, D-IDP, NFR-SEC-06): 5
consecutive failed attempts locks the account for 15 minutes -- an
implementation detail recorded in docs/decisions/OPEN-QUESTIONS.md, not a
locked PRD number."""

from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app
from packages.platform.auth.password_hashing import hash_password
from packages.platform.settings import Settings


@pytest_asyncio.fixture
async def app(engine, _database_url):
    settings = Settings(database_url=_database_url)
    application = create_app(settings)
    application.state.engine = engine
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def user_with_password(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('member') RETURNING id"))).scalar()
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES ('carol', 'Carol', :r, :h)"),
            {"r": role_id, "h": hash_password("real-password")},
        )
    return "carol"


async def test_five_failed_attempts_lock_the_account(client, user_with_password):
    for _ in range(5):
        response = await client.post("/auth/login", json={"username": "carol", "password": "wrong"})
        assert response.status_code == 401

    locked = await client.post("/auth/login", json={"username": "carol", "password": "wrong"})
    assert locked.status_code == 401
    assert locked.json()["error"]["code"] == "account_locked"


async def test_locked_account_rejects_even_the_correct_password(client, user_with_password):
    for _ in range(5):
        await client.post("/auth/login", json={"username": "carol", "password": "wrong"})

    still_locked = await client.post("/auth/login", json={"username": "carol", "password": "real-password"})
    assert still_locked.status_code == 401
    assert still_locked.json()["error"]["code"] == "account_locked"


async def test_successful_login_resets_the_failure_counter(client, user_with_password):
    for _ in range(3):
        await client.post("/auth/login", json={"username": "carol", "password": "wrong"})

    success = await client.post("/auth/login", json={"username": "carol", "password": "real-password"})
    assert success.status_code == 200

    await client.post("/auth/logout")
    for _ in range(4):
        response = await client.post("/auth/login", json={"username": "carol", "password": "wrong"})
        assert response.status_code == 401
        assert response.json()["error"]["code"] == "unauthenticated"


async def test_lock_clears_once_locked_until_has_passed(client, engine, user_with_password):
    for _ in range(5):
        await client.post("/auth/login", json={"username": "carol", "password": "wrong"})

    async with engine.begin() as conn:
        await conn.execute(text("UPDATE users SET locked_until = now() - interval '1 minute' WHERE username = 'carol'"))

    response = await client.post("/auth/login", json={"username": "carol", "password": "real-password"})
    assert response.status_code == 200
