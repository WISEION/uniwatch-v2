"""End-to-end over real HTTP: any pilot role can submit feedback
(platform.feedback.submit), only a triage role can list/resolve it
(platform.feedback.triage) -- RBAC deny-by-default (FR-ADM-01/02),
idempotency (FR-PLT-03), Phase 6 task 6.D's "training materials and
feedback queue for pilot users" result."""

from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app
from packages.platform.auth.password_hashing import hash_password
from packages.platform.settings import Settings

TEST_PASSWORD = "test-password-123"


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


async def _make_user(engine, *, username: str, permissions: tuple[str, ...]) -> None:
    async with engine.begin() as conn:
        role_id = (
            await conn.execute(text("INSERT INTO roles (name) VALUES (:name) RETURNING id"), {"name": f"role-{username}"})
        ).scalar()
        for perm in permissions:
            perm_row = (await conn.execute(text("SELECT id FROM permissions WHERE name = :name"), {"name": perm})).first()
            perm_id = perm_row[0] if perm_row else None
            if perm_id is None:
                perm_id = (
                    await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
                ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES (:u, :u, :r, :ph)"),
            {"u": username, "r": role_id, "ph": hash_password(TEST_PASSWORD)},
        )


async def _login(client: httpx.AsyncClient, username: str) -> None:
    response = await client.post("/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text


async def test_submitter_without_permission_is_denied(client, engine):
    await _make_user(engine, username="no-perms", permissions=())
    await _login(client, "no-perms")
    response = await client.post(
        "/pilot-feedback",
        json={"category": "bug", "message": "something broke"},
        headers={"Idempotency-Key": "k1"},
    )
    assert response.status_code == 403


async def test_submitter_with_permission_can_submit(client, engine):
    await _make_user(engine, username="submitter-1", permissions=("platform.feedback.submit",))
    await _login(client, "submitter-1")
    response = await client.post(
        "/pilot-feedback",
        json={"category": "bug", "message": "login button is misaligned"},
        headers={"Idempotency-Key": "k2"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["submitted_by"] == "submitter-1"
    assert body["category"] == "bug"
    assert body["status"] == "open"
    assert body["resolved_at"] is None


async def test_submit_rejects_an_unknown_category(client, engine):
    await _make_user(engine, username="submitter-2", permissions=("platform.feedback.submit",))
    await _login(client, "submitter-2")
    response = await client.post(
        "/pilot-feedback",
        json={"category": "not_a_real_category", "message": "x"},
        headers={"Idempotency-Key": "k3"},
    )
    assert response.status_code == 422


async def test_submit_is_idempotent(client, engine):
    await _make_user(engine, username="submitter-3", permissions=("platform.feedback.submit",))
    await _login(client, "submitter-3")
    payload = {"category": "question", "message": "how do I export a policy version?"}
    headers = {"Idempotency-Key": "k4"}
    first = await client.post("/pilot-feedback", json=payload, headers=headers)
    second = await client.post("/pilot-feedback", json=payload, headers=headers)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["id"] == second.json()["id"]


async def test_submitter_without_triage_permission_cannot_list_or_resolve(client, engine):
    await _make_user(engine, username="submitter-4", permissions=("platform.feedback.submit",))
    await _login(client, "submitter-4")
    submitted = await client.post(
        "/pilot-feedback",
        json={"category": "other", "message": "x"},
        headers={"Idempotency-Key": "k5"},
    )
    feedback_id = submitted.json()["id"]

    list_response = await client.get("/pilot-feedback")
    assert list_response.status_code == 403

    resolve_response = await client.post(f"/pilot-feedback/{feedback_id}/resolve", json={"resolution_note": "n/a"})
    assert resolve_response.status_code == 403


async def test_triage_role_can_list_and_resolve_feedback_submitted_by_another_user(client, engine):
    await _make_user(engine, username="submitter-5", permissions=("platform.feedback.submit",))
    await _make_user(engine, username="triager-1", permissions=("platform.feedback.triage",))

    await _login(client, "submitter-5")
    submitted = await client.post(
        "/pilot-feedback",
        json={"category": "feature_request", "message": "add dark mode"},
        headers={"Idempotency-Key": "k6"},
    )
    feedback_id = submitted.json()["id"]
    await client.post("/auth/logout")

    await _login(client, "triager-1")
    list_response = await client.get("/pilot-feedback", params={"status": "open"})
    assert list_response.status_code == 200
    assert any(item["id"] == feedback_id for item in list_response.json()["items"])

    resolve_response = await client.post(
        f"/pilot-feedback/{feedback_id}/resolve",
        json={"resolution_note": "added to the Phase 7 backlog"},
    )
    assert resolve_response.status_code == 200
    body = resolve_response.json()
    assert body["status"] == "resolved"
    assert body["resolved_by"] == "triager-1"
    assert body["resolution_note"] == "added to the Phase 7 backlog"
    assert body["resolved_at"] is not None

    still_open = await client.get("/pilot-feedback", params={"status": "open"})
    assert all(item["id"] != feedback_id for item in still_open.json()["items"])


async def test_resolving_an_unknown_feedback_id_is_404(client, engine):
    await _make_user(engine, username="triager-2", permissions=("platform.feedback.triage",))
    await _login(client, "triager-2")
    response = await client.post("/pilot-feedback/999999/resolve", json={"resolution_note": "n/a"})
    assert response.status_code == 404
