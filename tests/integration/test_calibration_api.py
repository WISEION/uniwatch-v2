"""End-to-end over real HTTP for task 4.D's outcome / loss-reason /
overhead-buffer / forecast-snapshot / calibration routes
(packages/decision/calibration_model.py, calibration_store.py,
calibration_summary.py). Fixtures follow tests/integration/test_decision_api.py
-- GET /calibration needs a real in-process Vendor service (same
httpx.ASGITransport wiring as test_decision_api.py's `client`); every other
route in this module ignores it."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from decimal import Decimal

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from apps.api_vendor.main import create_app as create_vendor_app
from packages.decision.calibration_store import load_tender_outcome
from packages.decision.decision_model import Decision
from packages.decision.decision_store import store_decision
from packages.decision.execution_ledger_store import store_overhead_buffer_contribution
from packages.platform.auth.password_hashing import hash_password
from packages.platform.settings import Settings
from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot
from packages.tender.signal_model import Signal
from packages.tender.signals_store import store_signal
from packages.vendor.reputation_model import ReputationFact
from packages.vendor.reputation_store import store_reputation_fact
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor

CALIBRATION_PERMISSIONS = (
    "decision.outcome.write",
    "decision.outcome.read",
    "tender.forecast_snapshot.write",
    "tender.forecast_snapshot.read",
)

NOW = datetime(2026, 8, 11, tzinfo=UTC).isoformat()

# Phase 6 task 6.A (D-IDP): a fixed, arbitrary test password shared by every
# user this file seeds.
TEST_PASSWORD = "test-password-123"


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


async def _auth(client: httpx.AsyncClient, username: str) -> dict:
    """Logs the given user in for real (Phase 6 task 6.A, D-IDP replaced the
    dev-only X-Dev-User header with a session-cookie login) and returns an
    empty headers dict so every call site below stays a minimal
    `await _auth(client, actor)` edit rather than a restructure."""
    response = await client.post("/auth/login", json={"username": username, "password": TEST_PASSWORD})
    assert response.status_code == 200, response.text
    return {}


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_vendor_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def client(tender_app, vendor_app):
    vendor_transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    vendor_client = httpx.AsyncClient(transport=vendor_transport, base_url="http://vendor-test")
    tender_app.state.vendor_http_client = vendor_client
    tender_app.state.settings = Settings(
        database_url=tender_app.state.settings.database_url,
        vendor_service_base_url="http://vendor-test",
    )
    tender_transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tender_transport, base_url="http://tender-test") as c:
        yield c
    await vendor_client.aclose()


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
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES ('pm-1', 'PM One', :r, :ph)"),
            {"r": role_id, "ph": hash_password(TEST_PASSWORD)},
        )
    return "pm-1"


@pytest_asyncio.fixture
async def user_without_permissions(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('no-calibration-perms') RETURNING id"))).scalar()
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id, password_hash) VALUES ('no-perms-1', 'No Perms', :r, :ph)"),
            {"r": role_id, "ph": hash_password(TEST_PASSWORD)},
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


async def _make_decided_tender_with_voen(engine, *, identity_key: str, event_id: int, organization_voen: str) -> int:
    """Same tender_versions.normalized_fields['organization_voen'] shape as
    test_execution_ledger_store.py's
    test_list_execution_facts_by_organization_voen_matches_across_tenders --
    list_outcomes_by_organization_voen joins through the identical
    latest-tender_version query."""
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
            conn,
            tender_id=tender_id,
            raw_snapshot_id=raw_snapshot_id,
            parser_version="v1",
            normalized_fields={"id": event_id, "organization_voen": organization_voen},
        )
        await store_decision(
            conn,
            Decision(
                tender_id=tender_id,
                decision_type="bid",
                conditions=(),
                deadline=None,
                justification="organization rollup test fixture",
                actor="pm-1",
                decided_at=NOW,
                go_no_go_inputs_id=None,
                bid_readiness_candidate_id=None,
            ),
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


@pytest_asyncio.fixture
async def decided_tender_id_with_boq(engine):
    """Same shape as test_decision_api.py's tender_with_boq, plus a bid
    decision -- GET /calibration's cost-basis path needs a real BOQ line to
    run match_boq_line/list_vendor_offers against."""
    line = BoqLine(
        source_line_id=1,
        page_number=1,
        section=None,
        category_code=None,
        description="Supply of rebar-12mm reinforcement steel",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )
    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-calibration-api-tender-with-boq",
            raw_body=json.dumps({"eventId": 103}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-calibration-api-tender-with-boq",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-calibration-api-tender-with-boq")
        version = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={"id": 103}
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=103,
            tender_version_id=version.id,
            raw_snapshot_id=raw_snapshot_id,
            lines=[line],
        )
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
async def two_strong_vendors(engine):
    """Same shape as test_decision_api.py's two_strong_vendors -- two
    reserved, fresh, sufficient-volume offers on rebar-12mm, one carrying a
    positive ReputationFact."""
    async with engine.begin() as conn:
        for name, seed in [("Vendor A", 1), ("Vendor B", 2)]:
            vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name=name, provider_type="synthetic", seed=seed)
            vendor_id, _api_key = await store_vendor(conn, vendor)
            offer = Offer(
                vendor_name=name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="rebar-12mm",
                price=850.0,
                currency="AZN",
                vat_rate=18.0,
                uom="t",
                uom_canonical_qty=1.0,
                moq=1.0,
                capacity=100.0,
                inventory=50.0,
                valid_from="2026-08-01T00:00:00+00:00",
                valid_until="2026-09-01T00:00:00+00:00",
                evidence_source="test",
                observed_at="2026-08-01T00:00:00+00:00",
                adverse_case=None,
                executable_status="reserved",
            )
            await store_offer(conn, vendor_id, offer)
            if name == "Vendor A":
                fact = ReputationFact(
                    data_realm="vendor-sandbox",
                    watermark="SYNTHETIC",
                    vendor_name=name,
                    event_type="price_held_after_win",
                    project_ref=None,
                    source_ref="test-calibration-api",
                    observed_at="2026-08-01T00:00:00+00:00",
                    ttl_days=365,
                )
                await store_reputation_fact(conn, vendor_id, fact)


@pytest_asyncio.fixture
async def object_region_with_composite_signals(engine):
    """object_intersection.detect_intersection's is_composite is exactly
    '2+ distinct signal_types on one object' -- any two qualify, no
    particular pair is special."""
    region = "TEST-REGION-CALIBRATION"
    async with engine.begin() as conn:
        for signal_type, event_id in (("donor_pipeline_project", 201), ("design_tender", 202)):
            raw_snapshot_id = await save_raw_snapshot(
                conn,
                source="worldbank" if signal_type == "donor_pipeline_project" else "etender",
                resource_type=signal_type,
                identity_key=f"test-calibration-api-signal-{signal_type}",
                raw_body=json.dumps({"eventId": event_id}).encode("utf-8"),
                contract_version="v1",
                correlation_id=f"test-calibration-api-signal-{signal_type}",
            )
            await store_signal(
                conn,
                Signal(
                    signal_type=signal_type,
                    source="test",
                    raw_snapshot_id=raw_snapshot_id,
                    value={},
                    observed_at=NOW,
                    ttl_class="funding_decision",
                    confidence="official_source",
                    object_customer=None,
                    object_region=region,
                    object_project_type=None,
                    correlation_id=f"test-calibration-api-signal-{signal_type}",
                ),
            )
    return region


async def test_post_outcome_without_auth_is_401(client, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload())
    assert r.status_code == 401


async def test_post_outcome_authenticated_without_permission_is_403(client, user_without_permissions, decided_tender_id):
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, user_without_permissions)
    )
    assert r.status_code == 403


async def test_post_outcome_persists_and_audits(client, pm_user, decided_tender_id, engine):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
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
    r = await client.post(f"/tenders/{undecided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "tender_not_decided_bid"


async def test_second_outcome_is_409_not_a_500_from_the_unique_index(client, pm_user, decided_tender_id):
    first = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    assert first.status_code == 200
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "outcome_already_recorded"


async def test_unknown_outcome_value_is_422_not_500(client, pm_user, decided_tender_id):
    """4.C's sixth deferred item was exactly this defect on another route --
    validation left to the migration CHECK, surfacing as 500. Not repeated."""
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome", json=_payload(outcome="probably_lost"), headers=await _auth(client, pm_user)
    )
    assert r.status_code == 422


async def test_blank_source_ref_is_422_because_INV_15_requires_provenance(client, pm_user, decided_tender_id):
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome", json=_payload(source_ref="  "), headers=await _auth(client, pm_user)
    )
    assert r.status_code == 422


async def test_a_won_outcome_needs_no_winner_fields(client, pm_user, decided_tender_id):
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome",
        json=_payload(outcome="won", winner_name=None, winner_amount=None),
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 200
    assert r.json()["outcome"] == "won"


async def test_loss_reason_without_auth_is_401(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    # Log out so this check exercises a genuinely unauthenticated request --
    # httpx.AsyncClient's cookie jar would otherwise still carry pm_user's
    # session from the setup call above.
    await client.post("/auth/logout")
    r = await client.post(f"/tenders/{decided_tender_id}/outcome/loss-reasons", json={"loss_reason": "dumping", "note": "n"})
    assert r.status_code == 401


async def test_loss_reason_authenticated_without_permission_is_403(client, pm_user, user_without_permissions, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=await _auth(client, user_without_permissions),
    )
    assert r.status_code == 403


async def test_loss_reason_on_a_won_outcome_is_409(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(outcome="won"), headers=await _auth(client, pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "outcome_not_a_loss"


async def test_loss_reason_with_no_recorded_outcome_is_404(client, pm_user, decided_tender_id):
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "outcome_not_found"


async def test_other_loss_reason_without_a_note_is_422(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "other", "note": "   "},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 422


async def test_loss_reason_persists_and_audits(client, pm_user, decided_tender_id, engine):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "30% under our cost"},
        headers=await _auth(client, pm_user),
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
    r = await client.get(f"/tenders/{decided_tender_id}/outcome", headers=await _auth(client, pm_user))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "outcome_not_found"


async def test_get_outcome_returns_the_recorded_outcome(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    r = await client.get(f"/tenders/{decided_tender_id}/outcome", headers=await _auth(client, pm_user))
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
    r = await client.get(f"/tenders/{decided_tender_id}/overhead-buffer", headers=await _auth(client, pm_user))
    assert r.status_code == 200
    assert r.json()["items"][0]["fact_count"] == 2


async def test_get_overhead_buffer_is_empty_list_not_error_when_none_recorded(client, pm_user, decided_tender_id):
    r = await client.get(f"/tenders/{decided_tender_id}/overhead-buffer", headers=await _auth(client, pm_user))
    assert r.status_code == 200
    assert r.json()["items"] == []


async def test_post_forecast_snapshot_without_auth_is_401(client, object_region_with_composite_signals):
    r = await client.post("/forecast-snapshots", json={"object_region": object_region_with_composite_signals})
    assert r.status_code == 401


async def test_post_forecast_snapshot_authenticated_without_permission_is_403(
    client, user_without_permissions, object_region_with_composite_signals
):
    r = await client.post(
        "/forecast-snapshots",
        json={"object_region": object_region_with_composite_signals},
        headers=await _auth(client, user_without_permissions),
    )
    assert r.status_code == 403


async def test_post_forecast_snapshot_below_threshold_is_409(client, pm_user):
    r = await client.post(
        "/forecast-snapshots", json={"object_region": "REGION-WITH-NO-SIGNALS"}, headers=await _auth(client, pm_user)
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "no_forecast_card"


async def test_post_forecast_snapshot_persists_and_audits(client, pm_user, object_region_with_composite_signals, engine):
    r = await client.post(
        "/forecast-snapshots",
        json={"object_region": object_region_with_composite_signals},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 200
    body = r.json()
    assert body["object_region"] == object_region_with_composite_signals
    assert body["is_composite"] is True
    assert sorted(body["signal_types"]) == ["design_tender", "donor_pipeline_project"]

    async with engine.begin() as conn:
        audit = (
            (await conn.execute(text("SELECT action FROM audit_log WHERE object_id = :oid"), {"oid": str(body["id"])}))
            .scalars()
            .all()
        )
    assert "calibration.record_forecast_snapshot" in audit


async def test_get_forecast_snapshot_without_auth_is_401(client, pm_user, object_region_with_composite_signals):
    r = await client.post(
        "/forecast-snapshots", json={"object_region": object_region_with_composite_signals}, headers=await _auth(client, pm_user)
    )
    snapshot_id = r.json()["id"]
    # Log out so this check exercises a genuinely unauthenticated request --
    # httpx.AsyncClient's cookie jar would otherwise still carry pm_user's
    # session from the setup call above.
    await client.post("/auth/logout")
    r = await client.get(f"/forecast-snapshots/{snapshot_id}")
    assert r.status_code == 401


async def test_get_forecast_snapshot_returns_404_for_unknown_id(client, pm_user):
    r = await client.get("/forecast-snapshots/999999999", headers=await _auth(client, pm_user))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "forecast_snapshot_not_found"


async def test_forecast_tender_link_without_auth_is_401(client, pm_user, object_region_with_composite_signals, decided_tender_id):
    r = await client.post(
        "/forecast-snapshots", json={"object_region": object_region_with_composite_signals}, headers=await _auth(client, pm_user)
    )
    snapshot_id = r.json()["id"]
    # Log out so this check exercises a genuinely unauthenticated request --
    # httpx.AsyncClient's cookie jar would otherwise still carry pm_user's
    # session from the setup call above.
    await client.post("/auth/logout")
    r = await client.post(f"/forecast-snapshots/{snapshot_id}/tender-link", json={"tender_id": decided_tender_id, "note": "n"})
    assert r.status_code == 401


async def test_forecast_tender_link_authenticated_without_permission_is_403(
    client, pm_user, user_without_permissions, object_region_with_composite_signals, decided_tender_id
):
    r = await client.post(
        "/forecast-snapshots", json={"object_region": object_region_with_composite_signals}, headers=await _auth(client, pm_user)
    )
    snapshot_id = r.json()["id"]
    r = await client.post(
        f"/forecast-snapshots/{snapshot_id}/tender-link",
        json={"tender_id": decided_tender_id, "note": "n"},
        headers=await _auth(client, user_without_permissions),
    )
    assert r.status_code == 403


async def test_forecast_tender_link_for_unknown_snapshot_is_404(client, pm_user, decided_tender_id):
    r = await client.post(
        "/forecast-snapshots/999999999/tender-link",
        json={"tender_id": decided_tender_id, "note": "n"},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "forecast_snapshot_not_found"


async def test_forecast_tender_link_persists_audits_and_exposes_observed_lag(
    client, pm_user, object_region_with_composite_signals, decided_tender_id, engine
):
    snapshot_response = await client.post(
        "/forecast-snapshots", json={"object_region": object_region_with_composite_signals}, headers=await _auth(client, pm_user)
    )
    snapshot_id = snapshot_response.json()["id"]

    link_response = await client.post(
        f"/forecast-snapshots/{snapshot_id}/tender-link",
        json={"tender_id": decided_tender_id, "note": "same road section, same buyer"},
        headers=await _auth(client, pm_user),
    )
    assert link_response.status_code == 200
    link_body = link_response.json()
    assert link_body["tender_id"] == decided_tender_id
    assert link_body["confirmed_by"] == "pm-1"
    # Both signals in object_region_with_composite_signals were observed at
    # NOW ("2026-08-11T...") -- decided_tender_id's tenders.created_at is set
    # by save_raw_snapshot/get_or_create_tender at fixture-creation time
    # (now()), which happens after NOW, so the lag is >= 0, never negative
    # or absent.
    assert link_body["observed_lag_days"] is not None
    assert link_body["observed_lag_days"] >= 0
    assert link_body["first_observed_at"] is not None

    async with engine.begin() as conn:
        audit = (
            (await conn.execute(text("SELECT action FROM audit_log WHERE object_id = :oid"), {"oid": str(link_body["id"])}))
            .scalars()
            .all()
        )
    assert "calibration.confirm_forecast_tender_link" in audit

    detail_response = await client.get(f"/forecast-snapshots/{snapshot_id}", headers=await _auth(client, pm_user))
    assert detail_response.status_code == 200
    detail_body = detail_response.json()
    assert len(detail_body["links"]) == 1
    assert detail_body["links"][0]["observed_lag_days"] == link_body["observed_lag_days"]


async def test_duplicate_forecast_tender_link_is_409_not_a_500_from_the_unique_constraint(
    client, pm_user, object_region_with_composite_signals, decided_tender_id
):
    snapshot_response = await client.post(
        "/forecast-snapshots", json={"object_region": object_region_with_composite_signals}, headers=await _auth(client, pm_user)
    )
    snapshot_id = snapshot_response.json()["id"]

    first = await client.post(
        f"/forecast-snapshots/{snapshot_id}/tender-link",
        json={"tender_id": decided_tender_id, "note": "n"},
        headers=await _auth(client, pm_user),
    )
    assert first.status_code == 200

    second = await client.post(
        f"/forecast-snapshots/{snapshot_id}/tender-link",
        json={"tender_id": decided_tender_id, "note": "n again"},
        headers=await _auth(client, pm_user),
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "tender_link_already_confirmed"


async def test_get_calibration_without_auth_is_401(client, decided_tender_id_with_boq):
    r = await client.get(f"/tenders/{decided_tender_id_with_boq}/calibration", params={"as_of": "2026-08-08T00:00:00Z"})
    assert r.status_code == 401


async def test_get_calibration_authenticated_without_permission_is_403(
    client, user_without_permissions, decided_tender_id_with_boq
):
    r = await client.get(
        f"/tenders/{decided_tender_id_with_boq}/calibration",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers=await _auth(client, user_without_permissions),
    )
    assert r.status_code == 403


async def test_get_calibration_rejects_naive_as_of(client, pm_user, decided_tender_id_with_boq):
    r = await client.get(
        f"/tenders/{decided_tender_id_with_boq}/calibration",
        params={"as_of": "2026-08-08T00:00:00"},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "naive_datetime"


async def test_get_calibration_returns_404_when_no_outcome_recorded(client, pm_user, decided_tender_id_with_boq):
    r = await client.get(
        f"/tenders/{decided_tender_id_with_boq}/calibration",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "outcome_not_found"


async def test_get_calibration_returns_price_comparison_with_coverage_and_loss_rollup(
    client, pm_user, decided_tender_id_with_boq, two_strong_vendors
):
    await client.post(f"/tenders/{decided_tender_id_with_boq}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    await client.post(
        f"/tenders/{decided_tender_id_with_boq}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "30% under our cost"},
        headers=await _auth(client, pm_user),
    )

    r = await client.get(
        f"/tenders/{decided_tender_id_with_boq}/calibration",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers=await _auth(client, pm_user),
    )
    assert r.status_code == 200
    body = r.json()

    assert body["outcome"]["outcome"] == "lost"
    assert body["loss_reason_rollup"] == {"dumping": 1}

    comparison = body["price_comparison"]
    # The one BOQ line (qty=10) has two strong, fresh, sufficient offers at
    # 850 AZN + 18% VAT -- match_boq_line's own TCO ranking picks the
    # cheapest, same currency candidate: 850 * 1.18 * 10 = 10030.
    assert Decimal(comparison["our_scg_cost_basis"]) == Decimal("10030")
    assert Decimal(comparison["winner_vs_our_submitted"]) == Decimal("98000.00") - Decimal("120000.00")
    assert Decimal(comparison["winner_vs_our_cost_basis"]) == Decimal("98000.00") - Decimal("10030")
    assert comparison["coverage_line_count"] == 1
    assert comparison["total_line_count"] == 1
    # Full coverage on this tender's one matchable line -- not partial.
    assert comparison["is_partial_coverage"] is False


async def test_get_organization_outcomes_without_auth_is_401(client):
    r = await client.get("/organizations/1000000001/outcomes")
    assert r.status_code == 401


async def test_get_organization_outcomes_authenticated_without_permission_is_403(client, user_without_permissions):
    r = await client.get("/organizations/1000000001/outcomes", headers=await _auth(client, user_without_permissions))
    assert r.status_code == 403


async def test_get_organization_outcomes_matches_across_tenders_and_carries_loss_reasons(client, pm_user, engine):
    tender_a = await _make_decided_tender_with_voen(
        engine, identity_key="test-calibration-api-org-a", event_id=301, organization_voen="1000000001"
    )
    tender_b = await _make_decided_tender_with_voen(
        engine, identity_key="test-calibration-api-org-b", event_id=302, organization_voen="1000000001"
    )
    tender_c = await _make_decided_tender_with_voen(
        engine, identity_key="test-calibration-api-org-c", event_id=303, organization_voen="9999999999"
    )

    await client.post(f"/tenders/{tender_a}/outcome", json=_payload(), headers=await _auth(client, pm_user))
    await client.post(
        f"/tenders/{tender_a}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "30% under our cost"},
        headers=await _auth(client, pm_user),
    )
    await client.post(
        f"/tenders/{tender_b}/outcome",
        json=_payload(outcome="won", winner_name=None, winner_amount=None),
        headers=await _auth(client, pm_user),
    )
    # A different buyer (VOEN) -- must not appear in "1000000001"'s rollup.
    await client.post(f"/tenders/{tender_c}/outcome", json=_payload(), headers=await _auth(client, pm_user))

    r = await client.get("/organizations/1000000001/outcomes", headers=await _auth(client, pm_user))
    assert r.status_code == 200
    body = r.json()

    tender_ids = {item["outcome"]["tender_id"] for item in body["items"]}
    assert tender_ids == {tender_a, tender_b}

    item_a = next(item for item in body["items"] if item["outcome"]["tender_id"] == tender_a)
    assert [lr["loss_reason"] for lr in item_a["loss_reasons"]] == ["dumping"]

    item_b = next(item for item in body["items"] if item["outcome"]["tender_id"] == tender_b)
    assert item_b["outcome"]["outcome"] == "won"
    assert item_b["loss_reasons"] == []
