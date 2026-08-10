"""End-to-end over real HTTP for task 4.C's Execution Ledger routes:
evidence-first capture (INV-18), voice-capture-is-never-parsed, an
unconfigured OCR backend as a real 503 (hard ban #3), and a simple list
read -- same fixture shape as tests/integration/test_decision_api.py."""

from __future__ import annotations

import base64
from decimal import Decimal

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from apps.api_vendor.main import create_app as create_vendor_app
from packages.decision.decision_model import Decision
from packages.decision.decision_store import store_decision, store_lock_in_requirement
from packages.platform.settings import Settings
from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

EXECUTION_LEDGER_PERMISSIONS = ("decision.execution_facts.create", "decision.execution_facts.read")


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
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
        expected_schema_version=16,
        vendor_service_base_url="http://vendor-test",
    )
    tender_transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tender_transport, base_url="http://tender-test") as c:
        yield c
    await vendor_client.aclose()


@pytest_asyncio.fixture
async def pm_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('pm-el') RETURNING id"))).scalar()
        for perm in EXECUTION_LEDGER_PERMISSIONS:
            perm_id = (
                await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('pm-el-1', 'PM EL', :r)"), {"r": role_id}
        )
    return "pm-el-1"


@pytest_asyncio.fixture
async def tender_with_boq_and_lock_in(engine):
    line = BoqLine(
        source_line_id=501,
        page_number=1,
        section=None,
        category_code=None,
        description="Rebar 12mm, grade B500B",
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
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-api-1",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-api-1",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-api-1")
        version = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"id": 800001},
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=800001,
            tender_version_id=version.id,
            raw_snapshot_id=snapshot_id,
            lines=[line],
        )
        # lock_in_requirements.decision_id is a real FK to decisions -- a
        # decision row must exist first, not an arbitrary literal id.
        decision_id = await store_decision(
            conn,
            Decision(
                tender_id=tender_id,
                decision_type="bid",
                conditions=(),
                deadline=None,
                justification="test",
                actor="pm-el-1",
                decided_at="2026-08-10T00:00:00+00:00",
                go_no_go_inputs_id=None,
                bid_readiness_candidate_id=None,
            ),
        )
        await store_lock_in_requirement(
            conn,
            tender_id=tender_id,
            decision_id=decision_id,
            boqline_source_line_id=501,
            vendor_id=42,
            vendor_name="Acme Crane Co",
        )
    return tender_id


async def test_napkin_submission_requires_auth(client, tender_with_boq_and_lock_in):
    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"x").decode()},
    )
    assert response.status_code == 401


async def test_voice_capture_stores_evidence_but_is_not_parsed(client, pm_user, tender_with_boq_and_lock_in):
    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "voice", "mime_type": "audio/ogg", "image_base64": base64.b64encode(b"voice-bytes").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["parsed"] is False
    assert body["facts"] == []
    assert body["evidence_id"] is not None


async def test_photo_submission_returns_503_when_ocr_not_configured(client, pm_user, tender_with_boq_and_lock_in, monkeypatch):
    # Hard ban #3 (no silent fallback): an unconfigured OCR backend must be
    # a real, loud error, never a silent no-op or a guessed model name.
    monkeypatch.delenv("OCR_MODEL_NAME", raising=False)
    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ocr_not_configured"


async def test_list_execution_facts_returns_stored_facts(client, pm_user, tender_with_boq_and_lock_in, engine):
    from packages.decision.execution_fact_model import ExecutionFact
    from packages.decision.execution_ledger_store import store_execution_fact

    async with engine.begin() as conn:
        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_with_boq_and_lock_in,
                boqline_source_line_id=501,
                planned_qty=Decimal("10"),
                actual_qty=Decimal("15"),
                deviation_reason="used more rebar than planned",
                deviation_category=None,
                culprit_type="internal",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:1",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    response = await client.get(f"/tenders/{tender_with_boq_and_lock_in}/execution-facts", headers={"X-Dev-User": pm_user})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["boqline_source_line_id"] == 501
