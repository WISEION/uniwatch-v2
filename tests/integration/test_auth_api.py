"""End-to-end over real HTTP: local-auth login/logout (Phase 6, task 6.A,
D-IDP), replacing the former dev-only X-Dev-User header entirely."""

from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app
from packages.platform.auth.password_hashing import hash_password
from packages.platform.settings import Settings

ADMIN_PERMISSIONS = ("admin.users.create", "admin.users.read", "admin.users.set_password")


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
async def admin_role(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('admin') RETURNING id"))).scalar()
        for perm in ADMIN_PERMISSIONS:
            perm_id = (
                await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
    return role_id


@pytest_asyncio.fixture
async def user_with_password(engine, admin_role):
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES ('alice', 'Alice', :r, :h)"),
            {"r": admin_role, "h": hash_password("correct horse battery staple")},
        )
    return "alice"


async def test_full_login_use_logout_lifecycle(client, user_with_password):
    login = await client.post("/auth/login", json={"username": "alice", "password": "correct horse battery staple"})
    assert login.status_code == 200
    assert login.json() == {"username": "alice", "role": "admin"}
    assert "uniwatch_session" in client.cookies

    authenticated = await client.get("/admin/users")
    assert authenticated.status_code == 200

    logout = await client.post("/auth/logout")
    assert logout.status_code == 204

    after_logout = await client.get("/admin/users")
    assert after_logout.status_code == 401
    assert after_logout.json()["error"]["code"] == "unauthenticated"


async def test_login_rejects_wrong_password(client, user_with_password):
    response = await client.post("/auth/login", json={"username": "alice", "password": "wrong password"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_login_rejects_unknown_username_with_the_same_error_as_wrong_password(client, user_with_password):
    wrong_password = await client.post("/auth/login", json={"username": "alice", "password": "wrong"})
    unknown_user = await client.post("/auth/login", json={"username": "no-such-user", "password": "wrong"})
    # A login attempt must not reveal whether a username exists.
    assert wrong_password.status_code == unknown_user.status_code == 401
    assert wrong_password.json()["error"]["code"] == unknown_user.json()["error"]["code"] == "unauthenticated"


async def test_route_without_any_session_cookie_is_unauthenticated(client):
    response = await client.get("/admin/users")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_admin_set_password_then_login_with_new_password(client, engine, admin_role):
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES ('bob', 'Bob', :r, :h)"),
            {"r": admin_role, "h": hash_password("old-password")},
        )
        user_id = (await conn.execute(text("SELECT id FROM users WHERE username = 'bob'"))).scalar()
    admin_login = await client.post("/auth/login", json={"username": "bob", "password": "old-password"})
    assert admin_login.status_code == 200

    set_password = await client.post(f"/admin/users/{user_id}/set-password", json={"password": "new-password"})
    assert set_password.status_code == 204

    await client.post("/auth/logout")
    old_password_login = await client.post("/auth/login", json={"username": "bob", "password": "old-password"})
    assert old_password_login.status_code == 401

    new_password_login = await client.post("/auth/login", json={"username": "bob", "password": "new-password"})
    assert new_password_login.status_code == 200
