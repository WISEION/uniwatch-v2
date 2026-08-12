"""Integration tests for forecast-card snapshot persistence and
human-confirmed tender links (Phase 4, task 4.D, TENDER_INTELLIGENCE_SPEC.md
Section5.4/P310, Section7.4/P319)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio
from sqlalchemy import text

from packages.tender.forecast_card import ForecastCard
from packages.tender.forecast_snapshot_store import (
    confirm_forecast_tender_link,
    list_links_by_snapshot,
    load_forecast_card_snapshot,
    observed_lag_days,
    store_forecast_card_snapshot,
)
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

NOW = datetime(2026, 8, 11, tzinfo=UTC).isoformat()


def _card(evidence_observed_at: str = "2026-02-01T00:00:00+00:00") -> ForecastCard:
    return ForecastCard(
        object_region="ZAQATALA",
        is_composite=True,
        signal_types=frozenset({"donor_pipeline_project", "design_tender"}),
        budget_estimate={"source": "donor_pipeline_project", "total_amount_usd_text": "12,000,000"},
        evidence_chain=(
            {
                "signal_type": "donor_pipeline_project",
                "source": "worldbank",
                "observed_at": evidence_observed_at,
                "raw_snapshot_id": 1,
                "value": {},
            },
        ),
    )


@pytest_asyncio.fixture
async def seeded_tender_id(engine):
    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-forecast-snapshot-store-tender",
            raw_body=json.dumps({"eventId": 1}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-forecast-snapshot-store",
        )
        # 2026-08-11 pinned so test_observed_lag_is_measured... stays
        # deterministic (tenders.created_at defaults to now() otherwise).
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-forecast-snapshot-store-tender")
        await conn.execute(
            text("UPDATE tenders SET created_at = :created_at WHERE id = :id"),
            {"created_at": datetime.fromisoformat(NOW), "id": tender_id},
        )
        await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={"id": 1}
        )
    return tender_id


async def test_snapshot_round_trips_every_forecast_card_field(engine):
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, _card(), computed_at=NOW)
        loaded = await load_forecast_card_snapshot(conn, snapshot_id=snapshot_id)

    assert loaded is not None
    assert loaded["object_region"] == "ZAQATALA"
    assert loaded["is_composite"] is True
    assert sorted(loaded["signal_types"]) == ["design_tender", "donor_pipeline_project"]
    assert loaded["budget_estimate"]["total_amount_usd_text"] == "12,000,000"
    assert len(loaded["evidence_chain"]) == 1


async def test_human_confirmed_link_is_recorded_with_its_author(engine, seeded_tender_id):
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, _card(), computed_at=NOW)
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="same road section, same buyer",
            confirmed_by="pm@unico.az",
            confirmed_at=NOW,
        )
        links = await list_links_by_snapshot(conn, snapshot_id=snapshot_id)

    assert len(links) == 1
    assert links[0]["confirmed_by"] == "pm@unico.az"
    assert links[0]["tender_id"] == seeded_tender_id


async def test_duplicate_link_is_rejected_by_the_unique_constraint(engine, seeded_tender_id):
    from sqlalchemy.exc import IntegrityError

    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, _card(), computed_at=NOW)
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="n",
            confirmed_by="pm",
            confirmed_at=NOW,
        )

    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await confirm_forecast_tender_link(
                conn,
                snapshot_id=snapshot_id,
                tender_id=seeded_tender_id,
                note="n",
                confirmed_by="pm",
                confirmed_at=NOW,
            )


async def test_observed_lag_is_measured_from_earliest_evidence_to_first_observed_at(engine, seeded_tender_id):
    """The measurement TBD-TIS-01/TBD-TIS-02 are blocked on. Nothing
    consumes it to adjust anything -- it is recorded, not applied."""
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(
            conn, _card(evidence_observed_at="2026-02-01T00:00:00+00:00"), computed_at=NOW
        )
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="n",
            confirmed_by="pm",
            confirmed_at=NOW,
        )
        lag = await observed_lag_days(conn, snapshot_id=snapshot_id, tender_id=seeded_tender_id)

    assert lag == 191  # 2026-02-01 -> 2026-08-11, pinned by the fixture


async def test_lag_is_none_when_no_evidence_carries_a_parseable_observed_at(engine, seeded_tender_id):
    """Hard ban #3: an unmeasurable lag is surfaced as missing, not 0."""
    card = ForecastCard(
        object_region="LERIK",
        is_composite=True,
        signal_types=frozenset({"design_tender", "procurement_plan"}),
        budget_estimate=None,
        evidence_chain=(
            {"signal_type": "design_tender", "source": "etender", "observed_at": None, "raw_snapshot_id": 2, "value": {}},
        ),
    )
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, card, computed_at=NOW)
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="n",
            confirmed_by="pm",
            confirmed_at=NOW,
        )
        assert await observed_lag_days(conn, snapshot_id=snapshot_id, tender_id=seeded_tender_id) is None
