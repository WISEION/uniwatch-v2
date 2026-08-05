"""TENDER_INTELLIGENCE_SPEC.md §5.3's "накопленные сигналы" (accumulated
signals) primitive: multiple independent observations about the same real
object must accumulate and be queryable together, regardless of
signal_type."""

from __future__ import annotations

import json

from source_fixtures import DESIGN_TENDER_QUERY_PARAMS, ETENDER_FIXTURES

from packages.tender.etender_connector import ingest_design_tender_signals_page
from packages.tender.signals_store import list_signals_by_object_region


async def test_zaqatala_accumulates_all_four_real_signals(engine):
    raw_body = (ETENDER_FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=DESIGN_TENDER_QUERY_PARAMS,
            correlation_id="corr-accum-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        rows = await list_signals_by_object_region(conn, object_region="Zaqatala")
        # Real fact: 4 of the 10 tenders on this page are all from Zaqatala Rayon İcra Hakimiyyəti
        # (events 356430, 356426, 356418, 356406) -- see MANIFEST.md.
        assert len(rows) == 4
        assert {row["value"]["event_id"] for row in rows} == {356430, 356426, 356418, 356406}
