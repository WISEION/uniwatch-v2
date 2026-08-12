"""Integration tests for calibration-loop persistence (Phase 4, task 4.D,
TENDER_INTELLIGENCE_SPEC.md Section7.4, P319)."""

from __future__ import annotations

import json
from datetime import UTC, datetime

import pytest
import pytest_asyncio

from packages.decision.calibration_model import LossReason, TenderOutcome
from packages.decision.calibration_store import (
    list_loss_reasons_by_outcome,
    list_overhead_buffer_contributions,
    load_tender_outcome,
    store_loss_reason,
    store_tender_outcome,
)
from packages.decision.execution_ledger_store import store_overhead_buffer_contribution
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

NOW = datetime(2026, 8, 11, tzinfo=UTC).isoformat()


@pytest_asyncio.fixture
async def seeded_tender_id(engine):
    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-calibration-store-tender",
            raw_body=json.dumps({"eventId": 1}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-calibration-store",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-calibration-store-tender")
        await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={"id": 1}
        )
    return tender_id


def _outcome(tender_id: int, **overrides) -> TenderOutcome:
    base = {
        "tender_id": tender_id,
        "outcome": "lost",
        "our_submitted_amount": "120000.00",
        "winner_name": "Rival LLC",
        "winner_amount": "98000.00",
        "currency": "AZN",
        "announced_at": NOW,
        "source_ref": "public award notice seen by PM",
        "entered_by": "pm@unico.az",
        "entered_at": NOW,
    }
    return TenderOutcome(**{**base, **overrides})


async def test_outcome_round_trips_with_amounts_intact(engine, seeded_tender_id):
    async with engine.begin() as conn:
        outcome_id = await store_tender_outcome(conn, _outcome(seeded_tender_id))
        loaded = await load_tender_outcome(conn, tender_id=seeded_tender_id)

    assert loaded is not None
    assert loaded["id"] == outcome_id
    assert loaded["outcome"] == "lost"
    # Decimal, not float -- money must not round-trip through binary float.
    assert str(loaded["our_submitted_amount"]) == "120000.00"
    assert str(loaded["winner_amount"]) == "98000.00"


async def test_missing_winner_amount_stays_none_and_is_not_coerced_to_zero(engine, seeded_tender_id):
    """Hard ban #3: a winner whose price the human does not know is
    'missing', which is a different fact from 'won for 0'."""
    async with engine.begin() as conn:
        await store_tender_outcome(conn, _outcome(seeded_tender_id, winner_amount=None))
        loaded = await load_tender_outcome(conn, tender_id=seeded_tender_id)

    assert loaded is not None
    assert loaded["winner_amount"] is None


async def test_load_returns_none_for_a_tender_with_no_recorded_outcome(engine, seeded_tender_id):
    async with engine.begin() as conn:
        assert await load_tender_outcome(conn, tender_id=seeded_tender_id) is None


async def test_second_outcome_for_one_tender_is_rejected_by_the_database(engine, seeded_tender_id):
    from sqlalchemy.exc import IntegrityError

    async with engine.begin() as conn:
        await store_tender_outcome(conn, _outcome(seeded_tender_id))

    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await store_tender_outcome(conn, _outcome(seeded_tender_id, outcome="won"))


async def test_multiple_loss_reasons_attach_to_one_outcome_in_insertion_order(engine, seeded_tender_id):
    async with engine.begin() as conn:
        outcome_id = await store_tender_outcome(conn, _outcome(seeded_tender_id))
        await store_loss_reason(
            conn,
            LossReason(loss_reason="dumping", note="30% under our cost", entered_by="pm", entered_at=NOW),
            tender_outcome_id=outcome_id,
        )
        await store_loss_reason(
            conn,
            LossReason(
                loss_reason="competitor_cheap_access",
                note="they own the quarry",
                entered_by="pm",
                entered_at=NOW,
            ),
            tender_outcome_id=outcome_id,
        )
        reasons = await list_loss_reasons_by_outcome(conn, tender_outcome_id=outcome_id)

    assert [r["loss_reason"] for r in reasons] == ["dumping", "competitor_cheap_access"]


async def test_overhead_buffer_contributions_are_readable(engine, seeded_tender_id):
    """Closes the write-only gap: nothing in the codebase ever SELECTed
    fact_count before this task."""
    async with engine.begin() as conn:
        await store_overhead_buffer_contribution(
            conn, tender_id=seeded_tender_id, deviation_category="downtime", fact_count=3, contributed_at=NOW
        )
        await store_overhead_buffer_contribution(
            conn, tender_id=seeded_tender_id, deviation_category="rework", fact_count=1, contributed_at=NOW
        )
        rows = await list_overhead_buffer_contributions(conn, tender_id=seeded_tender_id)

    assert {r["deviation_category"]: r["fact_count"] for r in rows} == {"downtime": 3, "rework": 1}
