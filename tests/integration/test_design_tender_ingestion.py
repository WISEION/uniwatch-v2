"""Derived design-tender signals over eTender's own already-proven
events-list ingestion (no new raw-ingestion contract, no new external
host) -- confirms only genuine design/TEO tenders on a real page produce
signals, real false positives are correctly excluded."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page
from packages.tender.signals_store import list_signals

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"

QUERY_PARAMS = {
    "EventType": "",
    "PageSize": 10,
    "EventStatus": 1,
    "Keyword": "layihə",
    "buyerOrganizationName": "",
    "documentNumber": "",
    "publishDateFrom": "",
    "publishDateTo": "",
    "AwardedparticipantName": "",
    "AwardedparticipantVoen": "",
    "DocumentViewType": "",
    "IsArchived": False,
}


async def test_page1_stores_signals_only_for_real_design_tenders(engine):
    raw_body = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=QUERY_PARAMS,
            correlation_id="corr-design-page1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        # Page 1 (per the fixture manifest) is entirely real design/TEO tenders --
        # confirm every item on it classifies True, not a hand-picked subset.
        assert len(signal_ids) == len(payload["items"])

        rows = await list_signals(conn, signal_type="design_tender")
        stored_event_ids = {row["value"]["event_id"] for row in rows}
        assert stored_event_ids == {item["eventId"] for item in payload["items"]}


async def test_page2_excludes_the_real_false_positives(engine):
    raw_body = (FIXTURES / "design_tender_search_page2.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=QUERY_PARAMS,
            correlation_id="corr-design-page2",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        # 4 real true negatives on this page (events 356291, 356027 -- plural "layihələr-";
        # 356048, 355959 -- unrelated uses of "layihə"), 6 real true positives.
        assert len(signal_ids) == 6

        rows = await list_signals(conn, signal_type="design_tender")
        stored_event_ids = {row["value"]["event_id"] for row in rows}
        assert stored_event_ids == {356192, 356143, 356140, 356055, 356039, 355972}
