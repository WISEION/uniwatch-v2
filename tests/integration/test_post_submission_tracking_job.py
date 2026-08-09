from __future__ import annotations

import json
from decimal import Decimal

from sqlalchemy import text

from packages.tender.boq_line_model import build_boq_lines
from packages.tender.boq_lines_store import list_boq_lines_by_event, store_boq_lines
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
        # Direct DB proof (not just the inferred flagged_line_count == 0 /
        # fetch_bom_page-raises-if-called signals above): a no-op check must
        # write zero rows to either append-only table.
        change_event_count = (
            await conn.execute(text("SELECT count(*) FROM tender_change_events WHERE tender_id = :tid"), {"tid": tender_id})
        ).scalar_one()
        recalc_flag_count = (
            await conn.execute(text("SELECT count(*) FROM boq_line_recalc_flags WHERE tender_id = :tid"), {"tid": tender_id})
        ).scalar_one()
    assert watch_state == "2026-08-09T12:00:00+00:00"
    assert change_event_count == 0
    assert recalc_flag_count == 0


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


async def test_schema_drift_on_refetch_is_queued_not_raised(engine):
    event_id = 700004
    async with engine.begin() as conn:
        await ingest_event_details(
            conn, raw_body=b"{}", payload=_details_payload(event_id, end_date=1788354059), correlation_id="test-4b-job-4"
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")

    async def fetch_event_details(eid):
        # Missing tenderName/organizationName/documentNumber -- all
        # non-optional in EVENT_DETAILS_CONTRACT, so this is real schema
        # drift (a source dropping fields), not a legitimate field change.
        payload = _details_payload(event_id, end_date=1788354059)
        del payload["tenderName"]
        del payload["organizationName"]
        del payload["documentNumber"]
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        raise AssertionError("must not be called -- drift blocks normalization before any diff/re-walk")

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-4",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result == {"change_detected": False, "change_type": None, "flagged_line_count": 0}

    async with engine.begin() as conn:
        watch_state = await get_watch_state(conn, tender_id=tender_id)
        exception_rows = (
            (
                await conn.execute(
                    text(
                        "SELECT source, exception_type, category, status FROM exception_queue "
                        "WHERE correlation_id = :correlation_id"
                    ),
                    {"correlation_id": "test-4b-job-4"},
                )
            )
            .mappings()
            .all()
        )

    # Watch state still advances -- a source-side drift must not cause this
    # tender to be immediately re-enqueued on the very next poll cycle.
    assert watch_state == "2026-08-09T12:00:00+00:00"
    assert len(exception_rows) == 1
    assert exception_rows[0]["source"] == "etender"
    assert exception_rows[0]["exception_type"] == "schema_drift"
    assert exception_rows[0]["category"] == "needs_human"
    assert exception_rows[0]["status"] == "open"


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
        # Built through the SAME build_boq_lines pipeline used below for the
        # "new" re-fetched line (not a hand-constructed BoqLine with its own
        # rate/amount values) -- otherwise old.rate/old.amount would differ
        # from new.rate/new.amount (both None, since _bom_item carries no
        # rate/amount key) for reasons unrelated to the qty change under
        # test, over-determining which field triggered the flag.
        [line] = build_boq_lines(page_number=1, items=[_bom_item(501, qty=10.0)])
        await store_boq_lines(
            conn,
            source="etender",
            event_id=event_id,
            tender_version_id=version.id,
            raw_snapshot_id=version.raw_snapshot_id,
            lines=[line],
        )
        raw_snapshot_count_before = (
            await conn.execute(text("SELECT count(*) FROM raw_snapshots WHERE resource_type = 'etender.bom_lines_page'"))
        ).scalar_one()

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
        stored_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id)
        # I2 review fix: the re-walked page must go through the SAME raw
        # evidence capture every other bom_lines ingestion in this codebase
        # gets (ADR-0003 layer-1) -- confirms a new raw_snapshots row landed
        # for the re-fetch, not just that build_boq_lines was called on
        # discarded bytes.
        raw_snapshot_count_after = (
            await conn.execute(text("SELECT count(*) FROM raw_snapshots WHERE resource_type = 'etender.bom_lines_page'"))
        ).scalar_one()

    assert [f["boqline_source_line_id"] for f in flags] == [501]
    assert len(stored_lines) == 1
    assert stored_lines[0].qty == Decimal("10")
    assert raw_snapshot_count_after == raw_snapshot_count_before + 1


async def test_heartbeat_is_called_once_per_bom_page(engine):
    event_id = 700005
    async with engine.begin() as conn:
        await ingest_event_details(
            conn,
            raw_body=b"{}",
            payload=_details_payload(event_id, end_date=1788354059, document_number="DOC-1"),
            correlation_id="test-4b-job-5",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")

    async def fetch_event_details(eid):
        # document_number changed -> triggers a re-walk of BOM pages, which
        # is the only place heartbeat() is called.
        payload = _details_payload(event_id, end_date=1788354059, document_number="DOC-2")
        return json.dumps(payload).encode("utf-8"), payload

    total_pages = 3

    async def fetch_bom_page(eid, page_number):
        payload = _bom_page_payload(event_id, page_number, total_pages=total_pages, items=[_bom_item(800 + page_number)])
        return json.dumps(payload).encode("utf-8"), payload

    heartbeat_calls = 0

    async def heartbeat():
        nonlocal heartbeat_calls
        heartbeat_calls += 1

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-5",
            observed_at="2026-08-09T12:00:00+00:00",
            heartbeat=heartbeat,
        )

    assert result["change_detected"] is True
    assert heartbeat_calls == total_pages


async def test_schema_drift_on_one_bom_page_does_not_block_the_others(engine):
    event_id = 700006
    async with engine.begin() as conn:
        await ingest_event_details(
            conn,
            raw_body=b"{}",
            payload=_details_payload(event_id, end_date=1788354059, document_number="DOC-1"),
            correlation_id="test-4b-job-6",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")
        version = await ingest_bom_lines_page(
            conn,
            event_id=event_id,
            raw_body=b"{}",
            payload=_bom_page_payload(event_id, 1, 2, [_bom_item(601, qty=10.0)]),
            correlation_id="test-4b-job-6",
        )
        old_lines = build_boq_lines(page_number=1, items=[_bom_item(601, qty=10.0)]) + build_boq_lines(
            page_number=2, items=[_bom_item(602, qty=20.0)]
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=event_id,
            tender_version_id=version.id,
            raw_snapshot_id=version.raw_snapshot_id,
            lines=old_lines,
        )

    async def fetch_event_details(eid):
        payload = _details_payload(event_id, end_date=1788354059, document_number="DOC-2")
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        if page_number == 1:
            # Page 1: real schema drift (a required BOM_LINE_ITEM_CONTRACT
            # field is missing), not a legitimate field change -- must not
            # crash the whole re-walk or block page 2 from being diffed.
            item = _bom_item(601, qty=10.0)
            del item["description"]
            payload = _bom_page_payload(event_id, 1, total_pages=2, items=[item])
        else:
            # Page 2: a real, valid qty change -- must still be correctly
            # diffed despite page 1's drift.
            payload = _bom_page_payload(event_id, 2, total_pages=2, items=[_bom_item(602, qty=99.0)])
        return json.dumps(payload).encode("utf-8"), payload

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-6",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    # Page 2's real change is still detected -- drift on page 1 did not stop
    # the re-walk from reaching/diffing page 2.
    assert result["change_detected"] is True

    async with engine.begin() as conn:
        flags = await list_unresolved_recalc_flags(conn, tender_id=tender_id)
        exception_rows = (
            (
                await conn.execute(
                    text(
                        "SELECT source, exception_type, category, status FROM exception_queue "
                        "WHERE correlation_id = :correlation_id"
                    ),
                    {"correlation_id": "test-4b-job-6"},
                )
            )
            .mappings()
            .all()
        )

    flagged_ids = {f["boqline_source_line_id"] for f in flags}
    assert 602 in flagged_ids
    assert len(exception_rows) == 1
    assert exception_rows[0]["source"] == "etender"
    assert exception_rows[0]["exception_type"] == "schema_drift"
    assert exception_rows[0]["category"] == "needs_human"
    assert exception_rows[0]["status"] == "open"
