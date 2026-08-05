"""Real proof that `build_object_region_forecast_card` assembles a genuine
evidence-chain card for Zaqatala (composite: design_tender + procurement_plan,
14 real signals, no donor_pipeline_project signal so budget_estimate is
honestly None) and returns None for Siyəzən (non-composite, same real
negative case task 2.C already proved) -- both from fixtures already
committed, no new live fetch needed."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page, ingest_procurement_plan_page
from packages.tender.signals_store import build_object_region_forecast_card

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"

DESIGN_QUERY_PARAMS = {
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


async def test_zaqatala_gets_a_real_evidence_chain_card_with_no_budget_estimate(engine):
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)
    app_raw = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    app_payload = json.loads(app_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_QUERY_PARAMS,
            correlation_id="corr-card-composite-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        await ingest_procurement_plan_page(
            conn,
            raw_body=app_raw,
            payload=app_payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-card-composite-2",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        card = await build_object_region_forecast_card(conn, object_region="Zaqatala")

    assert card is not None
    assert card.object_region == "Zaqatala"
    assert card.is_composite is True
    assert card.signal_types == frozenset({"design_tender", "procurement_plan"})
    assert card.budget_estimate is None
    assert len(card.evidence_chain) == 14
    assert {entry["signal_type"] for entry in card.evidence_chain} == {"design_tender", "procurement_plan"}


async def test_siyezen_gets_no_card(engine):
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_QUERY_PARAMS,
            correlation_id="corr-card-single-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        card = await build_object_region_forecast_card(conn, object_region="Siyəzən")

    assert card is None
