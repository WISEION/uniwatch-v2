from __future__ import annotations

import json
from decimal import Decimal

from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.change_tracking_store import get_watch_state, list_unresolved_recalc_flags
from packages.tender.etender_connector import ingest_bom_lines_page, ingest_event_details
from packages.tender.normalized import get_or_create_tender
from packages.tender.post_submission_tracking_job import check_tender_for_changes


def _details_payload(event_id: int, end_date: int, document_number: str = "DOC-1") -> dict:
    # Full EVENT_DETAILS_CONTRACT shape (etender_contract.py) -- every field
    # there is non-optional, so a re-fetch payload missing any of them would
    # be flagged as schema drift by ingest_event_details, not a real field
    # change. Values not under test (rfxId, address, ...) are arbitrary test
    # fixture data, not a TBD-nn/D-nn production constant.
    return {
        "id": event_id,
        "rfxId": 1,
        "eventId": event_id,
        "tenderName": "Test tender",
        "organizationName": "Test org",
        "organizationVoen": "1000000000",
        "envelopeDate": end_date,
        "endDate": end_date,
        "publishDate": end_date - 2000,
        "startDate": end_date - 1000,
        "budgetCategoryCode": None,
        "address": "Test address",
        "cpvCode": None,
        "eventType": 7,
        "isRedirectionAvailable": True,
        "minNumberOfSuppliers": 3,
        "estimatedAmount": 100000,
        "recreatedFromRfxId": None,
        "recreatedFromEventId": None,
        "documentNumber": document_number,
        "recreatedFromDocumentNumber": None,
        "evaluatedFinalScore": 50,
        "categoryCodes": ["72121400"],
    }


def _bom_page_payload(event_id: int, current_page: int, total_pages: int, items: list[dict]) -> dict:
    # Full BOM_LINES_PAGE_CONTRACT shape -- needed wherever this feeds
    # ingest_bom_lines_page (the test-setup step below); harmless extra
    # fields for the live-refetch path, which only reads items/totalPages.
    return {
        "currentPage": current_page,
        "totalPages": total_pages,
        "pageSize": 100,
        "totalItems": len(items),
        "itemsInPage": len(items),
        "items": items,
        "hasPreviousPage": current_page > 1,
        "hasNextPage": current_page < total_pages,
        "firstItem": 1 if items else 0,
        "lastItem": len(items),
    }


def _bom_item(item_id: int, qty: float = 10.0, description: str = "rebar-12mm") -> dict:
    # Matches BOM_LINE_ITEM_CONTRACT exactly (id/name/description/
    # unitOfMeasure/quantity/categoryCode) -- no rate/amount key, since the
    # real contract doesn't declare one and an extra key would itself be
    # flagged as drift by the test-setup ingest_bom_lines_page call below.
    return {
        "id": item_id,
        "name": None,
        "categoryCode": None,
        "description": description,
        "unitOfMeasure": "t",
        "quantity": qty,
    }


async def test_no_change_detected_when_refetch_is_identical(engine):
    event_id = 700001
    async with engine.begin() as conn:
        await ingest_event_details(
            conn, raw_body=b"{}", payload=_details_payload(event_id, end_date=1788354059), correlation_id="test-4b-job-1"
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")

    async def fetch_event_details(eid):
        assert eid == event_id
        payload = _details_payload(event_id, end_date=1788354059)
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        raise AssertionError("must not be called when event_details didn't change")

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-1",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result["change_detected"] is False
    assert result["flagged_line_count"] == 0

    async with engine.begin() as conn:
        watch_state = await get_watch_state(conn, tender_id=tender_id)
    assert watch_state == "2026-08-09T12:00:00+00:00"


async def test_deadline_shift_detected_and_recorded(engine):
    event_id = 700002
    async with engine.begin() as conn:
        await ingest_event_details(
            conn, raw_body=b"{}", payload=_details_payload(event_id, end_date=1788354059), correlation_id="test-4b-job-2"
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")

    async def fetch_event_details(eid):
        payload = _details_payload(event_id, end_date=1790000000)
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        payload = _bom_page_payload(event_id, page_number, total_pages=1, items=[_bom_item(1)])
        return json.dumps(payload).encode("utf-8"), payload

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-2",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result["change_detected"] is True
    assert result["change_type"] == "deadline_shift"


async def test_boq_line_change_is_flagged_without_mutating_boq_lines(engine):
    event_id = 700003
    async with engine.begin() as conn:
        await ingest_event_details(
            conn,
            raw_body=b"{}",
            payload=_details_payload(event_id, end_date=1788354059, document_number="DOC-1"),
            correlation_id="test-4b-job-3",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")
        version = await ingest_bom_lines_page(
            conn,
            event_id=event_id,
            raw_body=b"{}",
            payload=_bom_page_payload(event_id, 1, 1, [_bom_item(501, qty=10.0)]),
            correlation_id="test-4b-job-3",
        )
        line = BoqLine(
            source_line_id=501,
            page_number=1,
            section=None,
            category_code=None,
            description="rebar-12mm",
            unit_raw="t",
            unit_canonical="t",
            unit_status="mapped",
            qty=Decimal("10"),
            line_type="normal",
            spec_requirements=(),
            rate=Decimal("850"),
            amount=Decimal("8500"),
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=event_id,
            tender_version_id=version.id,
            raw_snapshot_id=version.raw_snapshot_id,
            lines=[line],
        )

    async def fetch_event_details(eid):
        # document_number changed -> triggers a re-walk of BOM pages
        payload = _details_payload(event_id, end_date=1788354059, document_number="DOC-2")
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        payload = _bom_page_payload(event_id, page_number, total_pages=1, items=[_bom_item(501, qty=15.0)])
        return json.dumps(payload).encode("utf-8"), payload

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-3",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result["flagged_line_count"] == 1

    async with engine.begin() as conn:
        flags = await list_unresolved_recalc_flags(conn, tender_id=tender_id)
        # boq_lines itself must be untouched -- still exactly the ORIGINAL
        # qty=10, never overwritten by the live re-fetch's qty=15.
        from packages.tender.boq_lines_store import list_boq_lines_by_event

        stored_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id)

    assert [f["boqline_source_line_id"] for f in flags] == [501]
    assert len(stored_lines) == 1
    assert stored_lines[0].qty == Decimal("10")
