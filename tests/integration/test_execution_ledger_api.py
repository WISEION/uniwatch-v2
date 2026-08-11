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


async def test_napkin_submission_rejected_when_tender_has_no_active_bid_decision(client, pm_user, engine):
    # TENDER_INTELLIGENCE_SPEC.md Section7.3 scopes the Execution Ledger to
    # an already-decided (bid/conditional_bid) tender -- a tender that was
    # never decided (or was decided no_bid) has no "plan" side for a
    # plan-vs-fact comparison to mean anything, so this must be rejected
    # before any evidence/OCR work happens, not silently accepted.
    from packages.tender.normalized import create_normalized_version, get_or_create_tender
    from packages.tender.raw_snapshot import save_raw_snapshot

    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-no-decision",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-no-decision",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-no-decision")
        await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"id": 900101},
        )

    response = await client.post(
        f"/tenders/{tender_id}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"x").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tender_not_decided_bid"

    async with engine.connect() as conn:
        evidence_rows = (
            (await conn.execute(text("SELECT id FROM execution_napkin_evidence WHERE tender_id = :t"), {"t": tender_id}))
            .mappings()
            .all()
        )
        assert evidence_rows == [], "rejected out-of-scope submission must not create an evidence row"


async def test_napkin_submission_rejected_when_tender_was_decided_no_bid(client, pm_user, engine):
    from packages.decision.decision_model import Decision
    from packages.decision.decision_store import store_decision
    from packages.tender.normalized import create_normalized_version, get_or_create_tender
    from packages.tender.raw_snapshot import save_raw_snapshot

    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-no-bid-decision",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-no-bid-decision",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-no-bid-decision")
        await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"id": 900102},
        )
        await store_decision(
            conn,
            Decision(
                tender_id=tender_id,
                decision_type="no_bid",
                conditions=(),
                deadline=None,
                justification="test",
                actor="pm-el-1",
                decided_at="2026-08-10T00:00:00+00:00",
                go_no_go_inputs_id=None,
                bid_readiness_candidate_id=None,
            ),
        )

    response = await client.post(
        f"/tenders/{tender_id}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"x").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tender_not_decided_bid"


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


async def test_two_unrelated_napkin_failures_on_the_same_tender_produce_two_exception_rows(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    # Final-review fix: correlation_id must come from the real ambient
    # per-request id (CorrelationIdMiddleware), not a synthetic
    # per-tender string -- otherwise enqueue_exception's get-or-create by
    # (source, exception_type, correlation_id, status='open') silently
    # merges a second, unrelated failure into the first still-open row.
    tender_app.state.ocr_engine = FakeOcrEngine("this is not valid json")
    first = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes-1").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert first.status_code == 422

    tender_app.state.ocr_engine = FakeOcrEngine(json.dumps({"not_observations": []}))
    second = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes-2").decode()},
        headers={"X-Dev-User": pm_user},
    )
    assert second.status_code == 422

    async with engine.connect() as conn:
        exception_rows = (
            (
                await conn.execute(
                    text(
                        "SELECT reason, correlation_id FROM exception_queue "
                        "WHERE exception_type = 'napkin_unrecognized' ORDER BY id"
                    )
                )
            )
            .mappings()
            .all()
        )
        assert len(exception_rows) == 2, "each distinct failure must get its own exception_queue row, not be merged"
        assert exception_rows[0]["correlation_id"] != exception_rows[1]["correlation_id"]
        assert "not valid JSON" in exception_rows[0]["reason"]
        assert "observations" in exception_rows[1]["reason"]


async def test_two_vendor_culprits_in_one_submission_each_get_their_own_exception_row(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    # Regression: enqueue_exception's get-or-create key is (source,
    # exception_type, correlation_id). Before the fix, every fact drafted
    # from ONE napkin submission shared the same request-level
    # correlation_id, so a second distinct vendor-culprit fact needing the
    # same exception_type (here: unresolved vendor name) would silently
    # collapse into the first fact's still-open row and its own reason
    # would be lost -- against hard ban #3 (no silent drops).
    ocr_payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 5,
                "deviation_reason": "first vendor never showed up",
                "deviation_category": "downtime",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Nonexistent Vendor One",
                "observed_at": "2026-08-10T00:00:00+00:00",
            },
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 5,
                "deviation_reason": "second vendor delivered wrong spec",
                "deviation_category": "rework",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Nonexistent Vendor Two",
                "observed_at": "2026-08-10T00:00:00+00:00",
            },
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
    assert len(response.json()["facts"]) == 2

    async with engine.connect() as conn:
        rows = (
            (
                await conn.execute(
                    text(
                        "SELECT reason, correlation_id FROM exception_queue "
                        "WHERE exception_type = 'vendor_reputation_unresolved_vendor' ORDER BY id"
                    )
                )
            )
            .mappings()
            .all()
        )
        assert len(rows) == 2, "each unresolved vendor culprit must get its own exception_queue row, not be merged"
        assert rows[0]["correlation_id"] != rows[1]["correlation_id"]
        reasons = {r["reason"] for r in rows}
        assert any("Nonexistent Vendor One" in r for r in reasons)
        assert any("Nonexistent Vendor Two" in r for r in reasons)


async def test_photo_submission_with_malformed_observed_at_is_422_and_durably_queued(
    client, tender_app, pm_user, tender_with_boq_and_lock_in, engine
):
    # Critical #2: an OCR/LLM-supplied non-ISO-8601 observed_at must never
    # reach datetime.fromisoformat(...) inside store_execution_fact
    # uncaught -- it must be caught as ExecutionNapkinParseError, same
    # 422 + durable exception-queue-row shape as the JSON-parse-failure
    # case above (INV-18: evidence and the failure reason both survive
    # the request-level rollback).
    ocr_payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 15,
                "deviation_reason": "used more rebar than planned",
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "10.08.2026",
            }
        ]
    }
    tender_app.state.ocr_engine = FakeOcrEngine(json.dumps(ocr_payload))

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
            (await conn.execute(text("SELECT reason FROM exception_queue WHERE exception_type = 'napkin_unrecognized'")))
            .mappings()
            .all()
        )
        assert len(exception_rows) == 1
        assert "observed_at" in exception_rows[0]["reason"]


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


async def test_close_project_is_not_idempotent_second_call_rejected(client, pm_user, tender_with_boq_and_lock_in, engine):
    # Final-review fix: overhead_buffer_contributions is append-only, so a
    # second close-project on the same tender must be rejected rather than
    # silently inserting a duplicate set of rows and doubling this
    # project's contribution to Phase 4.D's future calibration input.
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
                evidence_source="napkin-ocr:3",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    first = await client.post(f"/tenders/{tender_with_boq_and_lock_in}/close-project", headers={"X-Dev-User": pm_user})
    assert first.status_code == 200

    async with engine.begin() as conn:
        rows_after_first = (
            (
                await conn.execute(
                    text("SELECT id FROM overhead_buffer_contributions WHERE tender_id = :t"),
                    {"t": tender_with_boq_and_lock_in},
                )
            )
            .mappings()
            .all()
        )
    count_after_first = len(rows_after_first)
    assert count_after_first > 0

    second = await client.post(f"/tenders/{tender_with_boq_and_lock_in}/close-project", headers={"X-Dev-User": pm_user})
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "project_already_closed"

    async with engine.begin() as conn:
        rows_after_second = (
            (
                await conn.execute(
                    text("SELECT id FROM overhead_buffer_contributions WHERE tender_id = :t"),
                    {"t": tender_with_boq_and_lock_in},
                )
            )
            .mappings()
            .all()
        )
    assert len(rows_after_second) == count_after_first, "a rejected second close must not insert any additional rows"


async def test_close_project_rejected_when_tender_has_no_active_bid_decision(client, pm_user, engine):
    from packages.tender.normalized import create_normalized_version, get_or_create_tender
    from packages.tender.raw_snapshot import save_raw_snapshot

    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-close-no-decision",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-close-no-decision",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-close-no-decision")
        await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"id": 900103},
        )

    response = await client.post(f"/tenders/{tender_id}/close-project", headers={"X-Dev-User": pm_user})
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "tender_not_decided_bid"

    async with engine.connect() as conn:
        rows = (
            (await conn.execute(text("SELECT id FROM overhead_buffer_contributions WHERE tender_id = :t"), {"t": tender_id}))
            .mappings()
            .all()
        )
        assert rows == [], "a rejected close must not write any overhead-buffer contribution"


async def test_organization_execution_history_route_returns_matching_facts_and_requires_auth(client, pm_user, engine):
    from packages.decision.execution_fact_model import ExecutionFact
    from packages.decision.execution_ledger_store import store_execution_fact
    from packages.tender.normalized import create_normalized_version, get_or_create_tender
    from packages.tender.raw_snapshot import save_raw_snapshot

    # Same two-tenders-two-VOENs setup as
    # tests/integration/test_execution_ledger_store.py's
    # test_list_execution_facts_by_organization_voen_matches_across_tenders,
    # but driven through the real HTTP route instead of the store function.
    async with engine.begin() as conn:
        snapshot_a = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-org-route-a",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-org-route-a",
        )
        tender_a = await get_or_create_tender(conn, source="etender", identity_key="test-4c-org-route-a")
        await create_normalized_version(
            conn,
            tender_id=tender_a,
            raw_snapshot_id=snapshot_a,
            parser_version="v1",
            normalized_fields={"id": 900001, "organization_voen": "1234567890"},
        )

        snapshot_b = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-org-route-b",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-org-route-b",
        )
        tender_b = await get_or_create_tender(conn, source="etender", identity_key="test-4c-org-route-b")
        await create_normalized_version(
            conn,
            tender_id=tender_b,
            raw_snapshot_id=snapshot_b,
            parser_version="v1",
            normalized_fields={"id": 900002, "organization_voen": "9999999999"},
        )

        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_a,
                boqline_source_line_id=None,
                planned_qty=None,
                actual_qty=None,
                deviation_reason="site handover delayed by client",
                deviation_category="preliminaries",
                culprit_type="customer",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:org-route-a",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )
        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_b,
                boqline_source_line_id=None,
                planned_qty=None,
                actual_qty=None,
                deviation_reason="other buyer delayed handover",
                deviation_category="preliminaries",
                culprit_type="customer",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:org-route-b",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    unauth_response = await client.get("/organizations/1234567890/execution-history")
    assert unauth_response.status_code == 401

    response = await client.get("/organizations/1234567890/execution-history", headers={"X-Dev-User": pm_user})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["tender_id"] == tender_a
    assert body["items"][0]["deviation_reason"] == "site handover delayed by client"
