"""End-to-end over real HTTP for task 4.C's Execution Ledger routes:
evidence-first capture (INV-18), voice-capture-is-never-parsed, an
unconfigured OCR backend as a real 503 (hard ban #3), a simple list read,
and (review-fix round) the full OCR-parse/reputation-feed code path driven
by a fake OCR engine injected via `app.state.ocr_engine` (mirroring
`vendor_http_client`'s existing override pattern) -- same fixture shape as
tests/integration/test_decision_api.py."""

from __future__ import annotations

import base64
import json
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
from packages.vendor.vendor_model import Vendor
from packages.vendor.vendor_store import store_vendor

EXECUTION_LEDGER_PERMISSIONS = (
    "decision.execution_facts.create",
    "decision.execution_facts.read",
    "decision.execution_facts.close_project",
)


class FakeOcrEngine:
    """Test double for packages.platform.ocr_engine.OcrEngine -- returns a
    fixed response_text regardless of input, so tests can drive
    ExecutionNapkinProvider's parse/resolution logic deterministically
    without a real Ollama instance."""

    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        return self._response_text


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


@pytest_asyncio.fixture
async def tender_with_boq_lock_in_and_real_vendor(engine):
    """Same shape as tender_with_boq_and_lock_in, but the lock-in's
    vendor_id is a REAL row in `vendors` (via store_vendor) rather than the
    literal 42 -- vendor_reputation_facts.vendor_id is a real FK to
    vendors(id) in the (shared, in-process) Vendor service's own database,
    so a successful report_reputation_fact call needs a vendor that
    actually exists there, not just a lock-in requirement naming one."""
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
            identity_key="test-4c-api-real-vendor",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-api-real-vendor",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-api-real-vendor")
        version = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"id": 800002},
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=800002,
            tender_version_id=version.id,
            raw_snapshot_id=snapshot_id,
            lines=[line],
        )
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
        vendor = Vendor(
            data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Acme Crane Co", provider_type="synthetic", seed=42
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_lock_in_requirement(
            conn,
            tender_id=tender_id,
            decision_id=decision_id,
            boqline_source_line_id=501,
            vendor_id=vendor_id,
            vendor_name="Acme Crane Co",
        )
    return tender_id, vendor_id


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
    item = body["items"][0]
    assert item["boqline_source_line_id"] == 501
    assert item["tender_id"] == tender_with_boq_and_lock_in
    # Decimal precision must survive as a string, not be silently narrowed
    # to a float by FastAPI's jsonable_encoder (review-fix item 5) -- same
    # discipline the POST route's own response already applies.
    assert isinstance(item["planned_qty"], str)
    assert isinstance(item["actual_qty"], str)
    assert Decimal(item["planned_qty"]) == Decimal("10")
    assert Decimal(item["actual_qty"]) == Decimal("15")


async def test_napkin_unrecognized_still_persists_evidence_and_exception(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    # Critical review-fix regression guard: `conn` (Depends(get_connection))
    # rolls back the WHOLE request on the 422 raised below -- both the
    # evidence save and the napkin_unrecognized exception-queue row must
    # survive that rollback (they're each written through their own,
    # separately-committed transaction), or INV-18 is silently violated.
    tender_app.state.ocr_engine = FakeOcrEngine("this is not valid json")

    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "napkin_unrecognized"

    async with engine.connect() as conn:
        evidence_rows = (
            (
                await conn.execute(
                    text("SELECT id FROM execution_napkin_evidence WHERE tender_id = :t"),
                    {"t": tender_with_boq_and_lock_in},
                )
            )
            .mappings()
            .all()
        )
        assert len(evidence_rows) == 1, "evidence must be durable even though the request 422s (INV-18)"

        exception_rows = (
            (await conn.execute(text("SELECT reason, raw_ref FROM exception_queue WHERE exception_type = 'napkin_unrecognized'")))
            .mappings()
            .all()
        )
        assert len(exception_rows) == 1
        assert exception_rows[0]["raw_ref"] is None  # raw_ref is a raw_snapshots FK -- never evidence_id (item 2)


async def test_photo_submission_with_internal_culprit_stores_fact_without_reputation_call(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    ocr_payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 15,
                "deviation_reason": "used more rebar than planned",
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    tender_app.state.ocr_engine = FakeOcrEngine(json.dumps(ocr_payload))

    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["parsed"] is True
    assert len(body["facts"]) == 1
    fact = body["facts"][0]
    assert fact["culprit_type"] == "internal"
    assert fact["boqline_source_line_id"] == 501
    assert fact["planned_qty"] == "10"
    assert fact["actual_qty"] == "15"

    # An internal-culprit observation never maps to a reputation event --
    # no reputation-related exception_queue row should exist at all.
    async with engine.connect() as conn:
        rows = (
            (await conn.execute(text("SELECT exception_type FROM exception_queue WHERE source = 'execution-ledger'")))
            .mappings()
            .all()
        )
        assert rows == []


async def test_vendor_culprit_without_ttl_queues_exception_and_still_succeeds(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    ocr_payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 5,
                "deviation_reason": "late delivery caused downtime",
                "deviation_category": "downtime",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Acme Crane Co",
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    tender_app.state.ocr_engine = FakeOcrEngine(json.dumps(ocr_payload))

    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        # reputation_ttl_days deliberately omitted -- TBD-TIS-01.
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["facts"][0]["culprit_type"] == "vendor"
    assert body["facts"][0]["culprit_vendor_id"] == 42

    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text("SELECT reason FROM exception_queue WHERE exception_type = 'vendor_reputation_ttl_missing'")
                )
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1
        assert "42" in rows[0]["reason"]
        assert "missed_deadline" in rows[0]["reason"]
        assert "TBD-TIS-01" in rows[0]["reason"]

        reputation_rows = (await conn.execute(text("SELECT id FROM vendor_reputation_facts"))).mappings().all()
        assert reputation_rows == [], "no TTL was supplied -- report_reputation_fact must never be called"


async def test_vendor_culprit_with_unresolved_vendor_name_queues_exception(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    ocr_payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 5,
                "deviation_reason": "late delivery caused downtime",
                "deviation_category": "downtime",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Nonexistent Vendor Ltd",
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    tender_app.state.ocr_engine = FakeOcrEngine(json.dumps(ocr_payload))

    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={
            "capture_kind": "photo",
            "mime_type": "image/jpeg",
            "image_base64": base64.b64encode(b"jpeg-bytes").decode(),
            "reputation_ttl_days": 30,
        },
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 201
    assert response.json()["facts"][0]["culprit_vendor_id"] is None

    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text("SELECT reason FROM exception_queue WHERE exception_type = 'vendor_reputation_unresolved_vendor'")
                )
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1
        assert "Nonexistent Vendor Ltd" in rows[0]["reason"]

        reputation_rows = (await conn.execute(text("SELECT id FROM vendor_reputation_facts"))).mappings().all()
        assert reputation_rows == []


async def test_vendor_culprit_with_ttl_reports_reputation_fact_to_vendor_service(
    client, tender_app, pm_user, tender_with_boq_lock_in_and_real_vendor, engine
):
    tender_id, vendor_id = tender_with_boq_lock_in_and_real_vendor
    ocr_payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 5,
                "deviation_reason": "late delivery caused downtime",
                "deviation_category": "downtime",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Acme Crane Co",
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    tender_app.state.ocr_engine = FakeOcrEngine(json.dumps(ocr_payload))

    response = await client.post(
        f"/tenders/{tender_id}/execution-facts/napkin",
        json={
            "capture_kind": "photo",
            "mime_type": "image/jpeg",
            "image_base64": base64.b64encode(b"jpeg-bytes").decode(),
            "reputation_ttl_days": 30,
        },
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 201
    assert response.json()["facts"][0]["culprit_vendor_id"] == vendor_id

    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text("SELECT vendor_id, event_type, ttl_days, source_ref FROM vendor_reputation_facts WHERE vendor_id = :v"),
                    {"v": vendor_id},
                )
            )
            .mappings()
            .all()
        )
        assert len(rows) == 1
        assert rows[0]["event_type"] == "missed_deadline"
        assert rows[0]["ttl_days"] == 30
        assert rows[0]["source_ref"].startswith("napkin-ocr:")

        # No failure/ttl-missing exception should have been queued on the
        # success path.
        exc_rows = (
            (await conn.execute(text("SELECT exception_type FROM exception_queue WHERE source = 'execution-ledger'")))
            .mappings()
            .all()
        )
        assert exc_rows == []


async def test_execution_summary_reports_the_delta(client, pm_user, tender_with_boq_and_lock_in, engine):
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
                deviation_reason="more rebar used",
                deviation_category="rework",
                culprit_type="internal",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:1",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    response = await client.get(f"/tenders/{tender_with_boq_and_lock_in}/execution-summary", headers={"X-Dev-User": pm_user})
    assert response.status_code == 200
    body = response.json()
    assert body["plan_fact_deltas"][0]["delta"] == "5"
    assert body["deviation_category_counts"]["rework"] == 1


async def test_close_project_persists_overhead_buffer_contributions(client, pm_user, tender_with_boq_and_lock_in, engine):
    from packages.decision.execution_fact_model import ExecutionFact
    from packages.decision.execution_ledger_store import store_execution_fact

    async with engine.begin() as conn:
        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_with_boq_and_lock_in,
                boqline_source_line_id=None,
                planned_qty=None,
                actual_qty=None,
                deviation_reason="site handover delayed",
                deviation_category="preliminaries",
                culprit_type="customer",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:2",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    response = await client.post(f"/tenders/{tender_with_boq_and_lock_in}/close-project", headers={"X-Dev-User": pm_user})
    assert response.status_code == 200
    assert response.json()["deviation_category_counts"]["preliminaries"] == 1

    async with engine.begin() as conn:
        rows = (
            (
                await conn.execute(
                    text("SELECT deviation_category, fact_count FROM overhead_buffer_contributions WHERE tender_id = :t"),
                    {"t": tender_with_boq_and_lock_in},
                )
            )
            .mappings()
            .all()
        )
    assert any(r["deviation_category"] == "preliminaries" and r["fact_count"] == 1 for r in rows)
