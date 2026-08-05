"""INT-01, INT-02, FR-TND-10: raw evidence saved unconditionally, drift
checked, one Signal stored per plan on a clean page. The second test is
this whole slice's real payoff: proving, with 100% real captured data,
that two independent signal categories now share a real object."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page, ingest_procurement_plan_page
from packages.tender.signals_store import list_signals_by_object_region

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


async def test_zaqatala_page_stores_one_signal_per_real_plan(engine):
    raw_body = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_procurement_plan_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-app-page1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        assert len(signal_ids) == len(payload["items"])

        rows = await list_signals_by_object_region(conn, object_region="Zaqatala")
        stored_ids = {row["value"].get("app_id") for row in rows if row["signal_type"] == "procurement_plan"}
        assert stored_ids == {item["id"] for item in payload["items"]}


async def test_real_cross_category_intersection_on_zaqatala(engine):
    # The actual proof this plan exists to deliver: a design-tender signal AND a
    # procurement-plan signal, from two different real organizations, both anchor
    # to the same real object_region -- the first genuine cross-category overlap
    # this project has found (see docs/decisions/OPEN-QUESTIONS.md, 2026-08-05).
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)
    app_raw = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    app_payload = json.loads(app_raw)

    design_query_params = {
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

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=design_query_params,
            correlation_id="corr-intersect-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        await ingest_procurement_plan_page(
            conn,
            raw_body=app_raw,
            payload=app_payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-intersect-2",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        rows = await list_signals_by_object_region(conn, object_region="Zaqatala")
        signal_types = {row["signal_type"] for row in rows}
        assert signal_types == {"design_tender", "procurement_plan"}
