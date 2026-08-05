"""Real proof that `detect_object_region_intersection` correctly classifies a genuine
composite object (Zaqatala: design_tender + procurement_plan) against a genuine
non-composite one (Siyəzən: design_tender only) -- both cases from data already frozen
as fixtures, no new live fetch needed."""

from __future__ import annotations

import json

from source_fixtures import DESIGN_TENDER_QUERY_PARAMS, ETENDER_FIXTURES

from packages.tender.etender_connector import ingest_design_tender_signals_page, ingest_procurement_plan_page
from packages.tender.signals_store import detect_object_region_intersection


async def test_zaqatala_is_a_real_composite_intersection(engine):
    design_raw = (ETENDER_FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)
    app_raw = (ETENDER_FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    app_payload = json.loads(app_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_TENDER_QUERY_PARAMS,
            correlation_id="corr-intersection-composite-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        await ingest_procurement_plan_page(
            conn,
            raw_body=app_raw,
            payload=app_payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-intersection-composite-2",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        result = await detect_object_region_intersection(conn, object_region="Zaqatala")
        assert result.object_region == "Zaqatala"
        assert result.signal_types == frozenset({"design_tender", "procurement_plan"})
        assert result.is_composite is True


async def test_siyezen_is_a_real_non_composite_object(engine):
    # Real fact: page1's only Siyəzən tender (event 356386) has no matching
    # procurement-plan fixture -- exactly one signal_type, the honest
    # negative case for P310's "intersection, not a single signal" bar.
    design_raw = (ETENDER_FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_TENDER_QUERY_PARAMS,
            correlation_id="corr-intersection-single-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        result = await detect_object_region_intersection(conn, object_region="Siyəzən")
        assert result.signal_types == frozenset({"design_tender"})
        assert result.is_composite is False
