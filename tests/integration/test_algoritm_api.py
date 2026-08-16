"""End-to-end over real HTTP for task 5.D's АЛГОРИТМ routes
(apps/api_tender/routers/algoritm.py) -- the first HTTP surface over
packages/algorithm. Fixtures follow tests/integration/test_calibration_api.py's
shape (tender_app + real permission-granting user fixtures)."""

from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from packages.platform.auth.password_hashing import hash_password
from packages.platform.settings import Settings

ALL_ALGORITHM_PERMISSIONS = (
    "algorithm.policy.read",
    "algorithm.policy.write",
    "algorithm.policy.approve",
    "algorithm.policy.activate",
    "algorithm.simulation.read",
    "algorithm.simulation.write",
)

# Phase 6 task 6.A (D-IDP): a fixed, arbitrary test password shared by every
# user this file seeds.
TEST_PASSWORD = "test-password-123"


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def client(tender_app):
    transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://tender-test") as c:
        yield c


async def _make_user(engine, *, username: str, permissions: tuple[str, ...]) -> str:
    async with engine.begin() as conn:
        role_id = (
            await conn.execute(text("INSERT INTO roles (name) VALUES (:n) RETURNING id"), {"n": f"role-{username}"})
        ).scalar()
        for perm in permissions:
            existing = (await conn.execute(text("SELECT id FROM permissions WHERE name = :n"), {"n": perm})).scalar()
            perm_id = (
                existing
                or (
                    await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
                ).scalar()
            )
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES (:u, :u, :r, :ph)"),
            {"u": username, "r": role_id, "ph": hash_password(TEST_PASSWORD)},
        )
    return username


@pytest_asyncio.fixture
async def designer(engine):
    return await _make_user(engine, username="designer-1", permissions=ALL_ALGORITHM_PERMISSIONS)


@pytest_asyncio.fixture
async def checker(engine):
    return await _make_user(engine, username="checker-1", permissions=ALL_ALGORITHM_PERMISSIONS)


@pytest_asyncio.fixture
async def read_only_user(engine):
    return await _make_user(engine, username="reader-1", permissions=("algorithm.policy.read",))


async def _auth(client: httpx.AsyncClient, username: str) -> dict:
    """Logs the given user in for real (Phase 6 task 6.A, D-IDP replaced the
    dev-only X-Dev-User header with a session-cookie login) and returns an
    empty headers dict -- kept as a return value so every call site below
    stays a minimal `await _auth(client, actor)` edit rather than a
    restructure. httpx.AsyncClient's cookie jar then carries the session on
    every subsequent request on this same client, including across an
    identity switch (a later `_auth(client, other_user)` call just replaces
    the cookie via its own Set-Cookie response)."""
    response = await client.post("/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {}


def _rule_node(node_key: str, **overrides) -> dict:
    base = {
        "node_key": node_key,
        "node_type": "rule",
        "title": "Check amount",
        "purpose": "route by amount",
        "owner": "designer-1",
        "execution_mode": "automatic",
        "test_cases": [
            {"input": {"amount": 100}, "expected_output": {}, "covers_condition": "low"},
            {"input": {"amount": 900}, "expected_output": {}, "covers_condition": "high"},
        ],
    }
    base.update(overrides)
    return base


def _terminal_node(node_key: str) -> dict:
    return {
        "node_key": node_key,
        "node_type": "gate",
        "title": node_key,
        "purpose": "terminal",
        "owner": "designer-1",
        "execution_mode": "automatic",
    }


async def _build_clean_graph(client: httpx.AsyncClient, *, actor: str) -> tuple[int, int]:
    graph_resp = await client.post(
        "/policy-graphs", json={"name": "Bid/No-Bid test", "owner": actor}, headers=await _auth(client, actor)
    )
    assert graph_resp.status_code == 200, graph_resp.text
    graph_id = graph_resp.json()["id"]

    version_resp = await client.post(
        f"/policy-graphs/{graph_id}/versions", json={"version_number": 1}, headers=await _auth(client, actor)
    )
    assert version_resp.status_code == 200, version_resp.text
    version_id = version_resp.json()["id"]

    nodes = [_rule_node("start"), _terminal_node("low_path"), _terminal_node("high_path")]
    nodes_resp = await client.post(f"/policy-versions/{version_id}/nodes", json=nodes, headers=await _auth(client, actor))
    assert nodes_resp.status_code == 200, nodes_resp.text

    edges = [
        {"from_node_key": "start", "to_node_key": "low_path", "condition_label": "low"},
        {"from_node_key": "start", "to_node_key": "high_path", "condition_label": "high"},
    ]
    edges_resp = await client.post(f"/policy-versions/{version_id}/edges", json=edges, headers=await _auth(client, actor))
    assert edges_resp.status_code == 200, edges_resp.text

    return graph_id, version_id


async def test_full_lifecycle_to_active_with_maker_checker(client, designer, checker):
    _graph_id, version_id = await _build_clean_graph(client, actor=designer)

    validate_resp = await client.post(f"/policy-versions/{version_id}/validate", headers=await _auth(client, designer))
    assert validate_resp.status_code == 200
    assert validate_resp.json()["issues"] == []

    await client.post(
        f"/policy-versions/{version_id}/transition", json={"to_status": "simulation"}, headers=await _auth(client, designer)
    )
    await client.post(
        f"/policy-versions/{version_id}/transition", json={"to_status": "business_review"}, headers=await _auth(client, designer)
    )
    await client.post(
        f"/policy-versions/{version_id}/transition", json={"to_status": "risk_review"}, headers=await _auth(client, designer)
    )

    approve_resp = await client.post(
        f"/policy-versions/{version_id}/submit-for-approval", json={}, headers=await _auth(client, designer)
    )
    assert approve_resp.status_code == 200, approve_resp.text
    assert approve_resp.json()["status"] == "approved"

    same_identity_resp = await client.post(
        f"/policy-versions/{version_id}/activate", json={}, headers=await _auth(client, designer)
    )
    assert same_identity_resp.status_code == 200  # non-financial-impact node -- no maker/checker gate applies

    kill_resp = await client.post(
        f"/policy-versions/{version_id}/kill-switch",
        json={"reason": "manual test rehearsal"},
        headers=await _auth(client, checker),
    )
    assert kill_resp.status_code == 200
    assert kill_resp.json()["status"] == "suspended"

    transitions_resp = await client.get(f"/policy-versions/{version_id}/transitions", headers=await _auth(client, designer))
    assert transitions_resp.status_code == 200
    to_statuses = [t["to_status"] for t in transitions_resp.json()["items"]]
    assert to_statuses == ["simulation", "business_review", "risk_review", "approved", "active", "suspended"]


async def test_submit_for_approval_rejects_invalid_graph(client, designer):
    graph_resp = await client.post(
        "/policy-graphs", json={"name": "bad graph", "owner": designer}, headers=await _auth(client, designer)
    )
    graph_id = graph_resp.json()["id"]
    version_resp = await client.post(
        f"/policy-graphs/{graph_id}/versions", json={"version_number": 1}, headers=await _auth(client, designer)
    )
    version_id = version_resp.json()["id"]

    await client.post(
        f"/policy-versions/{version_id}/nodes", json=[_terminal_node("orphan_start")], headers=await _auth(client, designer)
    )
    await client.post(
        f"/policy-versions/{version_id}/edges",
        json=[{"from_node_key": "orphan_start", "to_node_key": "ghost", "condition_label": None}],
        headers=await _auth(client, designer),
    )

    validate_resp = await client.post(f"/policy-versions/{version_id}/validate", headers=await _auth(client, designer))
    assert any(i["code"] == "dangling_reference" for i in validate_resp.json()["issues"])

    for status in ("simulation", "business_review", "risk_review"):
        await client.post(
            f"/policy-versions/{version_id}/transition", json={"to_status": status}, headers=await _auth(client, designer)
        )

    approve_resp = await client.post(
        f"/policy-versions/{version_id}/submit-for-approval", json={}, headers=await _auth(client, designer)
    )
    assert approve_resp.status_code == 422
    body = approve_resp.json()
    assert body["error"]["code"] == "graph_invalid"
    assert any(d["code"] == "dangling_reference" for d in body["error"]["details"])


async def test_financial_impact_node_activation_requires_two_distinct_identities(client, designer, checker):
    graph_resp = await client.post(
        "/policy-graphs", json={"name": "financial policy", "owner": designer}, headers=await _auth(client, designer)
    )
    graph_id = graph_resp.json()["id"]
    version_resp = await client.post(
        f"/policy-graphs/{graph_id}/versions", json={"version_number": 1}, headers=await _auth(client, designer)
    )
    version_id = version_resp.json()["id"]

    dossier_resp = await client.post(
        "/research-dossiers",
        json={
            "decision_statement": "test-only dossier, not a real policy",
            "owners": ["designer-1"],
            "approvers": ["checker-1"],
            "source_register": [{"name": "test fixture", "citation": "n/a"}],
            "assumptions": ["none"],
            "data_dictionary": {},
            "formula_or_decision_table": {},
            "coefficients_and_rationale": {},
            "validation_design": {},
            "test_dataset_manifest": {},
            "results_and_limitations": {},
            "security_privacy_analysis": {},
            "monitoring_criteria": {},
            "retirement_criteria": {},
            "approved_at": "2026-08-14T00:00:00Z",
        },
        headers=await _auth(client, designer),
    )
    assert dossier_resp.status_code == 200, dossier_resp.text
    dossier_id = dossier_resp.json()["id"]
    await client.post(
        f"/policy-versions/{version_id}/link-dossier",
        json={"research_dossier_id": dossier_id},
        headers=await _auth(client, designer),
    )

    nodes = [_rule_node("start", financial_impact=True), _terminal_node("low_path"), _terminal_node("high_path")]
    await client.post(f"/policy-versions/{version_id}/nodes", json=nodes, headers=await _auth(client, designer))
    await client.post(
        f"/policy-versions/{version_id}/edges",
        json=[
            {"from_node_key": "start", "to_node_key": "low_path", "condition_label": "low"},
            {"from_node_key": "start", "to_node_key": "high_path", "condition_label": "high"},
        ],
        headers=await _auth(client, designer),
    )
    for status in ("simulation", "business_review", "risk_review"):
        await client.post(
            f"/policy-versions/{version_id}/transition", json={"to_status": status}, headers=await _auth(client, designer)
        )
    await client.post(f"/policy-versions/{version_id}/submit-for-approval", json={}, headers=await _auth(client, designer))

    same_identity_resp = await client.post(
        f"/policy-versions/{version_id}/activate", json={}, headers=await _auth(client, designer)
    )
    assert same_identity_resp.status_code == 409
    assert same_identity_resp.json()["error"]["code"] == "maker_checker_violation"

    different_identity_resp = await client.post(
        f"/policy-versions/{version_id}/activate", json={}, headers=await _auth(client, checker)
    )
    assert different_identity_resp.status_code == 200
    assert different_identity_resp.json()["status"] == "active"


async def test_simulate_and_read_back_case_traces(client, designer):
    _graph_id, version_id = await _build_clean_graph(client, actor=designer)

    simulate_resp = await client.post(
        f"/policy-versions/{version_id}/simulate",
        json={
            "case_set_label": "smoke-test",
            "case_source": "synthetic_vendor",
            "cases": [
                {"case_id": "low1", "inputs": {"amount": 100}, "actual_outcome_label": "won"},
                {"case_id": "high1", "inputs": {"amount": 900}, "actual_outcome_label": None},
            ],
        },
        headers=await _auth(client, designer),
    )
    assert simulate_resp.status_code == 200, simulate_resp.text
    run = simulate_resp.json()
    assert run["case_count"] == 2
    assert run["completed_count"] == 2
    assert run["terminal_distribution"] == {"low_path": 1, "high_path": 1}

    traces_resp = await client.get(f"/simulation-runs/{run['id']}/case-traces", headers=await _auth(client, designer))
    assert traces_resp.status_code == 200
    traces_by_case = {t["case_id"]: t for t in traces_resp.json()["items"]}
    assert traces_by_case["low1"]["terminal_node_key"] == "low_path"
    assert traces_by_case["low1"]["actual_outcome_label"] == "won"
    assert traces_by_case["high1"]["actual_outcome_label"] is None


async def test_compare_versions(client, designer):
    _graph_id, version_id = await _build_clean_graph(client, actor=designer)
    fork_resp = await client.post(f"/policy-versions/{version_id}/fork", headers=await _auth(client, designer))
    other_version_id = fork_resp.json()["id"]

    compare_resp = await client.post(
        f"/policy-versions/{version_id}/compare/{other_version_id}",
        json={"case_set_label": "identical-graphs", "cases": [{"case_id": "c1", "inputs": {"amount": 100}}]},
        headers=await _auth(client, designer),
    )
    assert compare_resp.status_code == 200, compare_resp.text
    assert compare_resp.json()["terminal_distribution"] == {"agree": 1, "disagree": 0}


async def test_read_only_user_cannot_write(client, read_only_user):
    resp = await client.post(
        "/policy-graphs", json={"name": "x", "owner": read_only_user}, headers=await _auth(client, read_only_user)
    )
    assert resp.status_code == 403


async def test_unauthenticated_request_is_rejected(client):
    resp = await client.get("/policy-graphs/1/versions")
    assert resp.status_code == 401
