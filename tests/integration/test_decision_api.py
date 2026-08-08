"""End-to-end over real HTTP for task 4.A's Decision Core routes: RBAC
deny-by-default, idempotency, a live bid-readiness-candidate computation
against a real in-process Vendor service (httpx.ASGITransport, same
pattern as tests/contract/test_tender_vendor_contract.py), and INV-20's
lock-in generation on a Bid decision."""

from __future__ import annotations

import json
from decimal import Decimal

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from apps.api_vendor.main import create_app as create_vendor_app
from packages.platform.settings import Settings
from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot
from packages.vendor.reputation_model import ReputationFact
from packages.vendor.reputation_store import store_reputation_fact
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor

DECISION_PERMISSIONS = (
    "decision.go_no_go.create",
    "decision.bid_readiness.read",
    "decision.decisions.create",
)


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=14)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=14)
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
        expected_schema_version=14,
        vendor_service_base_url="http://vendor-test",
    )
    tender_transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tender_transport, base_url="http://tender-test") as c:
        yield c
    await vendor_client.aclose()


@pytest_asyncio.fixture
async def pm_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('pm') RETURNING id"))).scalar()
        for perm in DECISION_PERMISSIONS:
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
async def user_without_decision_permissions(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('no-decision-perms') RETURNING id"))).scalar()
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('no-perms-1', 'No Perms', :r)"), {"r": role_id}
        )
    return "no-perms-1"


@pytest_asyncio.fixture
async def tender_with_boq(engine):
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
            identity_key="test-decision-api-tender",
            raw_body=json.dumps({"eventId": 42}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-decision-api",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-decision-api-tender")
        version = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        await store_boq_lines(
            conn, source="etender", event_id=42, tender_version_id=version.id, raw_snapshot_id=raw_snapshot_id, lines=[line]
        )
    return tender_id


@pytest_asyncio.fixture
async def two_strong_vendors(engine):
    # packages/decision/matching.py's _traffic_light requires >= 2 strong
    # (fresh, sufficient-volume, reserved/confirmed) sources AND at least
    # one of them carrying a positive ReputationFact to reach "green" --
    # "two strangers' prices give yellow" (P315) -- so Vendor A gets a
    # price_held_after_win fact to make this genuinely green, not yellow.
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
                    source_ref="test-decision-api",
                    observed_at="2026-08-01T00:00:00+00:00",
                    ttl_days=365,
                )
                await store_reputation_fact(conn, vendor_id, fact)


async def test_go_no_go_inputs_requires_auth(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json={
            "company_profile_notes": "x",
            "qualification_notes": "x",
            "financing_notes": "x",
            "customer_reputation_notes": "x",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k1"},
    )
    assert response.status_code == 401


async def test_go_no_go_inputs_creates_a_record(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json={
            "company_profile_notes": "20 years in market",
            "qualification_notes": "licenses current",
            "financing_notes": "bond available",
            "customer_reputation_notes": "pays on time",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k1", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["tender_id"] == tender_with_boq
    assert body["entered_by"] == "pm-1"


async def test_bid_readiness_candidate_computes_live_against_real_vendor_service(
    client, pm_user, tender_with_boq, two_strong_vendors
):
    response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["green_pct"] == 100.0
    assert body["is_lottery"] is False
    # Two strong vendors on the one BOQ line -- not single-vendor-critical.
    assert body["critical_lines"] == []


async def test_bid_readiness_candidate_flags_single_vendor_line_as_critical(client, pm_user, tender_with_boq, engine):
    async with engine.begin() as conn:
        vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Sole Vendor", provider_type="synthetic", seed=9)
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Sole Vendor",
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

    response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["critical_lines"]) == 1
    assert body["critical_lines"][0]["vendor_name"] == "Sole Vendor"


async def test_decision_with_bid_generates_lock_in_requirements(client, pm_user, tender_with_boq, engine):
    async with engine.begin() as conn:
        vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Sole Vendor", provider_type="synthetic", seed=9)
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Sole Vendor",
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

    candidate_response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )
    candidate_id = candidate_response.json()["id"]

    decision_response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={
            "decision_type": "bid",
            "conditions": [],
            "justification": "full coverage, single vendor accepted",
            "bid_readiness_candidate_id": candidate_id,
        },
        headers={"Idempotency-Key": "k-decision-1", "X-Dev-User": "pm-1"},
    )

    assert decision_response.status_code == 201
    body = decision_response.json()
    assert body["decision_type"] == "bid"
    assert len(body["lock_in_requirements"]) == 1
    assert body["lock_in_requirements"][0]["vendor_name"] == "Sole Vendor"
    assert body["lock_in_requirements"][0]["status"] == "pending"

    # The response's "status": "pending" is a hardcoded literal in the
    # router, not read back from the DB -- confirm a real row was persisted,
    # not just echoed in the HTTP response.
    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT decision_id, boqline_source_line_id, vendor_id, vendor_name, status "
                        "FROM lock_in_requirements WHERE tender_id = :tid"
                    ),
                    {"tid": tender_with_boq},
                )
            )
            .mappings()
            .first()
        )
    assert row is not None
    assert row["vendor_name"] == "Sole Vendor"
    assert row["decision_id"] == body["id"]
    assert row["status"] == "pending"


async def test_decision_rejects_unknown_decision_type(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={"decision_type": "maybe", "conditions": [], "justification": "x"},
        headers={"Idempotency-Key": "k-decision-2", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 422


async def test_decision_without_bid_type_does_not_generate_lock_ins(client, pm_user, tender_with_boq, engine):
    # Regression guard: the router's guard is
    # `decision_type in ("bid", "conditional_bid") AND bid_readiness_candidate_id is not None`
    # -- either half being false makes lock-in generation skip, so this test
    # must supply a REAL candidate that DOES have a critical line, proving
    # the decision_type ("no_go") is what suppresses lock-ins, not a missing
    # candidate id.
    async with engine.begin() as conn:
        vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Sole Vendor", provider_type="synthetic", seed=9)
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Sole Vendor",
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

    candidate_response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )
    candidate_id = candidate_response.json()["id"]
    assert len(candidate_response.json()["critical_lines"]) == 1  # confirms this candidate DOES have a critical line

    response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={
            "decision_type": "no_go",
            "conditions": [],
            "justification": "qualification stop",
            "bid_readiness_candidate_id": candidate_id,
        },
        headers={"Idempotency-Key": "k-decision-3", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 201
    assert response.json()["lock_in_requirements"] == []


async def test_bid_readiness_candidate_rejects_naive_as_of(client, pm_user, tender_with_boq):
    response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00"},
        headers={"X-Dev-User": "pm-1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "naive_datetime"


async def test_go_no_go_inputs_with_nonexistent_tender_returns_422(client, pm_user):
    response = await client.post(
        "/tenders/999999999/go-no-go-inputs",
        json={
            "company_profile_notes": "x",
            "qualification_notes": "x",
            "financing_notes": "x",
            "customer_reputation_notes": "x",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k-nonexistent-tender", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_reference"


async def test_mutations_write_audit_log_entries(client, pm_user, tender_with_boq, engine):
    go_no_go_response = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json={
            "company_profile_notes": "x",
            "qualification_notes": "x",
            "financing_notes": "x",
            "customer_reputation_notes": "x",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k-audit-go-no-go", "X-Dev-User": "pm-1"},
    )
    decision_response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={"decision_type": "no_go", "conditions": [], "justification": "audit trail check"},
        headers={"Idempotency-Key": "k-audit-decision", "X-Dev-User": "pm-1"},
    )

    async with engine.begin() as conn:
        rows = (
            (
                await conn.execute(
                    text(
                        "SELECT actor, action, object_type, object_id, reason FROM audit_log "
                        "WHERE action IN ('go_no_go_inputs.create', 'decision.create') ORDER BY id"
                    )
                )
            )
            .mappings()
            .all()
        )

    assert len(rows) == 2
    assert rows[0]["actor"] == "pm-1"
    assert rows[0]["action"] == "go_no_go_inputs.create"
    assert rows[0]["object_id"] == str(go_no_go_response.json()["id"])
    assert rows[1]["action"] == "decision.create"
    assert rows[1]["object_id"] == str(decision_response.json()["id"])
    assert rows[1]["reason"] == "audit trail check"


async def test_go_no_go_inputs_replay_with_same_idempotency_key_returns_same_response(client, pm_user, tender_with_boq, engine):
    payload = {
        "company_profile_notes": "20 years in market",
        "qualification_notes": "licenses current",
        "financing_notes": "bond available",
        "customer_reputation_notes": "pays on time",
        "pre_designated_winner_suspected": False,
    }
    first = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json=payload,
        headers={"Idempotency-Key": "k-replay-test", "X-Dev-User": "pm-1"},
    )
    second = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json=payload,
        headers={"Idempotency-Key": "k-replay-test", "X-Dev-User": "pm-1"},
    )

    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json() == second.json()

    async with engine.begin() as conn:
        count = (
            await conn.execute(text("SELECT count(*) FROM go_no_go_inputs WHERE tender_id = :tid"), {"tid": tender_with_boq})
        ).scalar_one()
    assert count == 1


async def test_go_no_go_inputs_without_permission_is_403(client, user_without_decision_permissions, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json={
            "company_profile_notes": "x",
            "qualification_notes": "x",
            "financing_notes": "x",
            "customer_reputation_notes": "x",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k-403-test", "X-Dev-User": "no-perms-1"},
    )
    assert response.status_code == 403
