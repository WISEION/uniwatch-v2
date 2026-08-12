"""End-to-end over real HTTP for task 4.D's outcome / loss-reason /
overhead-buffer routes (packages/decision/calibration_model.py,
calibration_store.py). Fixtures follow tests/integration/test_decision_api.py
-- this module needs no vendor app: none of these routes call the Vendor
service."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from packages.decision.calibration_store import load_tender_outcome
from packages.decision.decision_model import Decision
from packages.decision.decision_store import store_decision
from packages.decision.execution_ledger_store import store_overhead_buffer_contribution
from packages.platform.settings import Settings
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

CALIBRATION_PERMISSIONS = ("decision.outcome.write", "decision.outcome.read")

NOW = datetime(2026, 8, 11, tzinfo=UTC).isoformat()


def _payload(**overrides) -> dict:
    base = {
        "outcome": "lost",
        "our_submitted_amount": "120000.00",
        "winner_name": "Rival LLC",
        "winner_amount": "98000.00",
        "currency": "AZN",
        "announced_at": NOW,
        "source_ref": "etender public award page, screenshot in project folder",
    }
    return {**base, **overrides}


def _auth(username: str) -> dict:
    return {"X-Dev-User": username}


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


@pytest_asyncio.fixture
async def pm_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('pm-calibration') RETURNING id"))).scalar()
        for perm in CALIBRATION_PERMISSIONS:
            perm_id = (
                await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('pm-1', 'PM One', :r)"), {"r": role_id}
        )
    return "pm-1"


@pytest_asyncio.fixture
async def user_without_permissions(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('no-calibration-perms') RETURNING id"))).scalar()
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('no-perms-1', 'No Perms', :r)"), {"r": role_id}
        )
    return "no-perms-1"


async def _make_tender(engine, *, identity_key: str, event_id: int) -> int:
    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key=identity_key,
            raw_body=json.dumps({"eventId": event_id}).encode("utf-8"),
            contract_version="v1",
            correlation_id=f"test-calibration-api-{identity_key}",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)
        await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={"id": event_id}
        )
        return tender_id


@pytest_asyncio.fixture
async def decided_tender_id(engine):
    tender_id = await _make_tender(engine, identity_key="test-calibration-api-decided-tender", event_id=101)
    async with engine.begin() as conn:
        await store_decision(
            conn,
            Decision(
                tender_id=tender_id,
                decision_type="bid",
                conditions=(),
                deadline=None,
                justification="calibration api test fixture",
                actor="pm-1",
                decided_at=NOW,
                go_no_go_inputs_id=None,
                bid_readiness_candidate_id=None,
            ),
        )
    return tender_id


@pytest_asyncio.fixture
async def undecided_tender_id(engine):
    return await _make_tender(engine, identity_key="test-calibration-api-undecided-tender", event_id=102)


async def test_post_outcome_without_auth_is_401(client, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload())
    assert r.status_code == 401


async def test_post_outcome_authenticated_without_permission_is_403(client, user_without_permissions, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(user_without_permissions))
    assert r.status_code == 403


async def test_post_outcome_persists_and_audits(client, pm_user, decided_tender_id, engine):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert r.status_code == 200

    async with engine.begin() as conn:
        row = await load_tender_outcome(conn, tender_id=decided_tender_id)
        audit = (
            (await conn.execute(text("SELECT action FROM audit_log WHERE object_id = :oid"), {"oid": str(row["id"])}))
            .scalars()
            .all()
        )

    assert row is not None and row["outcome"] == "lost"
    assert "calibration.record_outcome" in audit


async def test_outcome_on_a_tender_with_no_bid_decision_is_409(client, pm_user, undecided_tender_id):
    r = await client.post(f"/tenders/{undecided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "tender_not_decided_bid"


async def test_second_outcome_is_409_not_a_500_from_the_unique_index(client, pm_user, decided_tender_id):
    first = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert first.status_code == 200
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "outcome_already_recorded"


async def test_unknown_outcome_value_is_422_not_500(client, pm_user, decided_tender_id):
    """4.C's sixth deferred item was exactly this defect on another route --
    validation left to the migration CHECK, surfacing as 500. Not repeated."""
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(outcome="probably_lost"), headers=_auth(pm_user))
    assert r.status_code == 422


async def test_blank_source_ref_is_422_because_INV_15_requires_provenance(client, pm_user, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(source_ref="  "), headers=_auth(pm_user))
    assert r.status_code == 422


async def test_a_won_outcome_needs_no_winner_fields(client, pm_user, decided_tender_id):
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome",
        json=_payload(outcome="won", winner_name=None, winner_amount=None),
        headers=_auth(pm_user),
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "won"


async def test_loss_reason_without_auth_is_401(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    r = await client.post(f"/tenders/{decided_tender_id}/outcome/loss-reasons", json={"loss_reason": "dumping", "note": "n"})
    assert r.status_code == 401


async def test_loss_reason_authenticated_without_permission_is_403(client, pm_user, user_without_permissions, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=_auth(user_without_permissions),
    )
    assert r.status_code == 403


async def test_loss_reason_on_a_won_outcome_is_409(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(outcome="won"), headers=_auth(pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=_auth(pm_user),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "outcome_not_a_loss"


async def test_loss_reason_with_no_recorded_outcome_is_404(client, pm_user, decided_tender_id):
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=_auth(pm_user),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "outcome_not_found"


async def test_other_loss_reason_without_a_note_is_422(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "other", "note": "   "},
        headers=_auth(pm_user),
    )
    assert r.status_code == 422


async def test_loss_reason_persists_and_audits(client, pm_user, decided_tender_id, engine):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "30% under our cost"},
        headers=_auth(pm_user),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["loss_reason"] == "dumping"

    async with engine.begin() as conn:
        audit = (
            (await conn.execute(text("SELECT action FROM audit_log WHERE object_id = :oid"), {"oid": str(body["id"])}))
            .scalars()
            .all()
        )
    assert "calibration.record_loss_reason" in audit


async def test_get_outcome_without_auth_is_401(client, decided_tender_id):
    r = await client.get(f"/tenders/{decided_tender_id}/outcome")
    assert r.status_code == 401


async def test_get_outcome_returns_404_when_none_recorded(client, pm_user, decided_tender_id):
    r = await client.get(f"/tenders/{decided_tender_id}/outcome", headers=_auth(pm_user))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "outcome_not_found"


async def test_get_outcome_returns_the_recorded_outcome(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    r = await client.get(f"/tenders/{decided_tender_id}/outcome", headers=_auth(pm_user))
    assert r.status_code == 200
    body = r.json()
    assert body["outcome"] == "lost"
    assert body["winner_amount"] == "98000.00"


async def test_get_overhead_buffer_without_auth_is_401(client, decided_tender_id):
    r = await client.get(f"/tenders/{decided_tender_id}/overhead-buffer")
    assert r.status_code == 401


async def test_get_overhead_buffer_returns_the_stored_counts(client, pm_user, decided_tender_id, engine):
    async with engine.begin() as conn:
        await store_overhead_buffer_contribution(
            conn, tender_id=decided_tender_id, deviation_category="downtime", fact_count=2, contributed_at=NOW
        )
    r = await client.get(f"/tenders/{decided_tender_id}/overhead-buffer", headers=_auth(pm_user))
    assert r.status_code == 200
    assert r.json()["items"][0]["fact_count"] == 2


async def test_get_overhead_buffer_is_empty_list_not_error_when_none_recorded(client, pm_user, decided_tender_id):
    r = await client.get(f"/tenders/{decided_tender_id}/overhead-buffer", headers=_auth(pm_user))
    assert r.status_code == 200
    assert r.json()["items"] == []
