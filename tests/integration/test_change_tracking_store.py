from __future__ import annotations

from packages.tender.change_tracking_store import (
    get_watch_state,
    list_unresolved_recalc_flags,
    store_boq_line_recalc_flag,
    store_tender_change_event,
    upsert_watch_state,
)
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot
from packages.tender.tender_change_detection import TenderFieldChange


async def _make_tender(conn, identity_key: str) -> int:
    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type="etender.event_details",
        identity_key=identity_key,
        raw_body=b"{}",
        contract_version="etender.event_details",
        correlation_id="test-4b-store",
    )
    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)
    await create_normalized_version(
        conn, tender_id=tender_id, raw_snapshot_id=snapshot_id, parser_version="v1", normalized_fields={}
    )
    return tender_id, snapshot_id


async def test_store_and_list_a_recalc_flag(engine):
    async with engine.begin() as conn:
        tender_id, snapshot_id = await _make_tender(conn, "test-4b-store-1")
        change_event_id = await store_tender_change_event(
            conn,
            tender_id=tender_id,
            change_type="deadline_shift",
            changed_fields=(TenderFieldChange(field="end_date", old_value=1, new_value=2),),
            detected_at="2026-08-09T00:00:00+00:00",
            raw_snapshot_id=snapshot_id,
        )
        await store_boq_line_recalc_flag(
            conn,
            tender_id=tender_id,
            boqline_source_line_id=501,
            change_event_id=change_event_id,
            flagged_at="2026-08-09T00:00:00+00:00",
        )
        flags = await list_unresolved_recalc_flags(conn, tender_id=tender_id)

    assert len(flags) == 1
    assert flags[0]["boqline_source_line_id"] == 501
    assert flags[0]["change_event_id"] == change_event_id


async def test_list_unresolved_recalc_flags_is_scoped_to_the_tender(engine):
    async with engine.begin() as conn:
        tender_a, snap_a = await _make_tender(conn, "test-4b-store-2a")
        tender_b, _snap_b = await _make_tender(conn, "test-4b-store-2b")
        event_a = await store_tender_change_event(
            conn,
            tender_id=tender_a,
            change_type="document_changed",
            changed_fields=(),
            detected_at="2026-08-09T00:00:00+00:00",
            raw_snapshot_id=snap_a,
        )
        await store_boq_line_recalc_flag(
            conn,
            tender_id=tender_a,
            boqline_source_line_id=1,
            change_event_id=event_a,
            flagged_at="2026-08-09T00:00:00+00:00",
        )

    async with engine.begin() as conn:
        flags_b = await list_unresolved_recalc_flags(conn, tender_id=tender_b)
    assert flags_b == []


async def test_watch_state_is_none_before_any_check(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-store-3")
        result = await get_watch_state(conn, tender_id=tender_id)
    assert result is None


async def test_upsert_watch_state_then_get_returns_the_latest_checked_at(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-store-4")
        await upsert_watch_state(conn, tender_id=tender_id, checked_at="2026-08-09T00:00:00+00:00")
        first = await get_watch_state(conn, tender_id=tender_id)
        await upsert_watch_state(conn, tender_id=tender_id, checked_at="2026-08-09T06:00:00+00:00")
        second = await get_watch_state(conn, tender_id=tender_id)

    assert first == "2026-08-09T00:00:00+00:00"
    assert second == "2026-08-09T06:00:00+00:00"
