"""End-to-end over real HTTP: idempotency (FR-PLT-03), cursor pagination
(FR-PLT-05), ETag precondition (FR-PLT-04), RBAC deny-by-default
(FR-ADM-01/02), disable-not-delete + audit (FR-ADM-04/05), command/query
separation (FR-PLT-02)."""

from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api.main import create_app
from packages.platform.settings import Settings

ADMIN_PERMISSIONS = (
    "admin.users.create",
    "admin.users.read",
    "admin.users.update",
    "admin.users.disable",
)


@pytest_asyncio.fixture
async def app(engine, _database_url):
    settings = Settings(database_url=_database_url)
    application = create_app(settings)
    application.state.engine = engine  # reuse the test engine/pool
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def admin_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('admin') RETURNING id"))).scalar()
        for perm in ADMIN_PERMISSIONS:
            perm_id = (
                await conn.execute(
                    text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"),
                    {"name": perm},
                )
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('admin-1', 'Admin One', :r)"),
            {"r": role_id},
        )
    return "admin-1"


@pytest_asyncio.fixture
async def viewer_role(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('member') RETURNING id"))).scalar()
    return role_id


async def test_get_without_dev_user_header_is_401(client, admin_user):
    response = await client.get("/admin/users")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_authenticated_user_without_permission_is_403(client, viewer_role, engine):
    async with engine.begin() as conn:
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('viewer-1', 'Viewer', :r)"),
            {"r": viewer_role},
        )
    response = await client.get("/admin/users", headers={"X-Dev-User": "viewer-1"})
    assert response.status_code == 403
    assert response.json()["error"]["code"] == "forbidden"


async def test_create_user_requires_idempotency_key(client, admin_user, viewer_role):
    response = await client.post(
        "/admin/users",
        json={"username": "new-1", "display_name": "New One", "role_name": "member"},
        headers={"X-Dev-User": admin_user},
    )
    assert response.status_code == 422  # missing required header


async def test_create_user_replay_does_not_duplicate(client, admin_user, viewer_role, engine):
    payload = {"username": "new-2", "display_name": "New Two", "role_name": "member"}
    headers = {"X-Dev-User": admin_user, "Idempotency-Key": "create-key-1"}

    first = await client.post("/admin/users", json=payload, headers=headers)
    assert first.status_code == 201
    second = await client.post("/admin/users", json=payload, headers=headers)
    assert second.status_code == 201
    assert first.json() == second.json()

    async with engine.begin() as conn:
        count = (await conn.execute(text("SELECT count(*) FROM users WHERE username = 'new-2'"))).scalar()
    assert count == 1


async def test_create_user_same_key_different_payload_is_conflict(client, admin_user, viewer_role):
    headers = {"X-Dev-User": admin_user, "Idempotency-Key": "create-key-2"}
    first = await client.post(
        "/admin/users",
        json={"username": "new-3", "display_name": "New Three", "role_name": "member"},
        headers=headers,
    )
    assert first.status_code == 201
    second = await client.post(
        "/admin/users",
        json={"username": "new-4", "display_name": "New Four", "role_name": "member"},
        headers=headers,
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "idempotency_key_reused"


async def test_list_users_paginates_by_cursor_not_offset(client, admin_user, viewer_role, engine):
    async with engine.begin() as conn:
        for i in range(5):
            await conn.execute(
                text("INSERT INTO users (username, display_name, role_id) VALUES (:u, :u, :r)"),
                {"u": f"bulk-{i}", "r": viewer_role},
            )

    headers = {"X-Dev-User": admin_user}
    first_page = await client.get("/admin/users?limit=2", headers=headers)
    assert first_page.status_code == 200
    body = first_page.json()
    assert len(body["items"]) == 2
    assert body["next_cursor"] is not None
    assert "offset" not in first_page.url.params

    second_page = await client.get(f"/admin/users?limit=2&cursor={body['next_cursor']}", headers=headers)
    second_body = second_page.json()
    assert len(second_body["items"]) == 2
    first_ids = {item["id"] for item in body["items"]}
    second_ids = {item["id"] for item in second_body["items"]}
    assert first_ids.isdisjoint(second_ids)


async def test_garbage_cursor_is_a_client_error_not_an_internal_error(client, admin_user):
    response = await client.get("/admin/users?cursor=not-a-real-cursor", headers={"X-Dev-User": admin_user})
    assert response.status_code == 400
    assert response.json()["error"]["code"] == "invalid_cursor"


async def test_get_never_writes_db_state(client, admin_user, viewer_role, engine):
    async def snapshot():
        async with engine.begin() as conn:
            return (await conn.execute(text("SELECT count(*) FROM users"))).scalar()

    before = await snapshot()
    for _ in range(3):
        response = await client.get("/admin/users", headers={"X-Dev-User": admin_user})
        assert response.status_code == 200
    after = await snapshot()
    assert before == after


async def test_update_without_if_match_is_422(client, admin_user, viewer_role, engine):
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("INSERT INTO users (username, display_name, role_id) VALUES ('u-upd', 'U', :r) RETURNING id"),
                {"r": viewer_role},
            )
        ).scalar()
    response = await client.patch(
        f"/admin/users/{user_id}",
        json={"display_name": "Renamed"},
        headers={"X-Dev-User": admin_user},
    )
    assert response.status_code == 422


async def test_update_with_stale_if_match_is_409_with_current_version(client, admin_user, viewer_role, engine):
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("INSERT INTO users (username, display_name, role_id) VALUES ('u-upd2', 'U', :r) RETURNING id"),
                {"r": viewer_role},
            )
        ).scalar()
    response = await client.patch(
        f"/admin/users/{user_id}",
        json={"display_name": "Renamed"},
        headers={"X-Dev-User": admin_user, "If-Match": "99"},
    )
    assert response.status_code == 409
    assert response.json()["error"]["details"] == [{"current_version": 1}]


async def test_update_with_correct_if_match_succeeds_and_bumps_version(client, admin_user, viewer_role, engine):
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("INSERT INTO users (username, display_name, role_id) VALUES ('u-upd3', 'U', :r) RETURNING id"),
                {"r": viewer_role},
            )
        ).scalar()
    response = await client.patch(
        f"/admin/users/{user_id}",
        json={"display_name": "Renamed"},
        headers={"X-Dev-User": admin_user, "If-Match": "1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["display_name"] == "Renamed"
    assert body["version"] == 2


async def test_disable_keeps_row_and_is_not_deletable(client, admin_user, viewer_role, engine):
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("INSERT INTO users (username, display_name, role_id) VALUES ('u-dis', 'U', :r) RETURNING id"),
                {"r": viewer_role},
            )
        ).scalar()
    response = await client.post(
        f"/admin/users/{user_id}/disable",
        json={"reason": "left the company"},
        headers={"X-Dev-User": admin_user},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "disabled"

    async with engine.begin() as conn:
        row = (await conn.execute(text("SELECT status FROM users WHERE id = :id"), {"id": user_id})).mappings().first()
        audit = (
            (
                await conn.execute(
                    text("SELECT action, reason FROM audit_log WHERE object_id = :id AND action = 'user.disable'"),
                    {"id": str(user_id)},
                )
            )
            .mappings()
            .first()
        )
    assert row is not None  # row still exists — no DELETE was issued
    assert row["status"] == "disabled"
    assert audit["reason"] == "left the company"


async def test_disabled_user_cannot_authenticate(client, admin_user, viewer_role, engine):
    async with engine.begin() as conn:
        user_id = (
            await conn.execute(
                text("INSERT INTO users (username, display_name, role_id) VALUES ('u-dis2', 'U', :r) RETURNING id"),
                {"r": viewer_role},
            )
        ).scalar()
    await client.post(
        f"/admin/users/{user_id}/disable",
        json={"reason": "n/a"},
        headers={"X-Dev-User": admin_user},
    )
    response = await client.get("/admin/users", headers={"X-Dev-User": "u-dis2"})
    assert response.status_code == 401
