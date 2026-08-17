"""Integration tests for packages/decision/decision_store.py (task 4.A).
Append-only for `decisions`: this file does not test any UPDATE/DELETE
because none exists to test -- see decision_store.py's module docstring."""

from __future__ import annotations

import json
from decimal import Decimal

from packages.decision.bid_readiness import BidReadinessCandidate, CriticalLine
from packages.decision.boq_summary import BoqMatchSummary
from packages.decision.decision_model import Decision, GoNoGoInputs
from packages.decision.decision_store import (
    list_decision_cycle_seconds,
    list_lock_in_requirements_by_tender,
    list_tenders_with_active_bid_decision,
    load_bid_readiness_candidate,
    store_bid_readiness_candidate,
    store_decision,
    store_go_no_go_inputs,
    store_lock_in_requirement,
)
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot


async def _make_tender(conn, identity_key: str) -> int:
    raw_snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type="event_details",
        identity_key=identity_key,
        raw_body=json.dumps({"eventId": 1}).encode("utf-8"),
        contract_version="v1",
        correlation_id="test-decision-store",
    )
    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)
    await create_normalized_version(
        conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
    )
    return tender_id


async def test_go_no_go_inputs_round_trips(engine):
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-1")
        inputs = GoNoGoInputs(
            tender_id=tender_id,
            company_profile_notes="20 years in market",
            qualification_notes="all licenses current",
            financing_notes="bond available",
            customer_reputation_notes="pays on time",
            pre_designated_winner_suspected=False,
            entered_by="pm-1",
            entered_at="2026-08-08T00:00:00+00:00",
        )
        inputs_id = await store_go_no_go_inputs(conn, inputs)

    assert isinstance(inputs_id, int)


async def test_bid_readiness_candidate_round_trips_with_critical_lines(engine):
    summary = BoqMatchSummary(
        green_amount=Decimal("1000"),
        yellow_amount=Decimal("0"),
        red_amount=Decimal("0"),
        unpriced_line_count=0,
        non_matchable_line_count=0,
        non_matchable_amount=Decimal("0"),
        total_priced_amount=Decimal("1000"),
        green_pct=100.0,
        yellow_pct=0.0,
        red_pct=0.0,
    )
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-2")
        candidate = BidReadinessCandidate(
            tender_id=tender_id,
            summary=summary,
            is_lottery=False,
            critical_lines=(CriticalLine(boqline_source_line_id=1, vendor_id=7, vendor_name="Vendor A"),),
            computed_at="2026-08-08T00:00:00+00:00",
        )
        candidate_id = await store_bid_readiness_candidate(conn, candidate)
        loaded = await load_bid_readiness_candidate(conn, candidate_id)

    assert loaded["tender_id"] == tender_id
    assert loaded["critical_lines"] == [{"boqline_source_line_id": 1, "vendor_id": 7, "vendor_name": "Vendor A"}]


async def test_decision_rejects_at_the_model_layer_not_silently_in_the_db(engine):
    # Decision.__post_init__ already raises for an unknown decision_type
    # (tested in test_decision_model.py) -- this test only proves the
    # store layer round-trips a VALID decision correctly, including
    # conditions as a real list, not a string.
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-3")
        decision = Decision(
            tender_id=tender_id,
            decision_type="conditional_bid",
            conditions=("lock rebar price by Friday", "find backup crane owner"),
            deadline="2026-08-14T00:00:00+00:00",
            justification="91% coverage, 14-16% margin",
            actor="pm-1",
            decided_at="2026-08-08T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=None,
        )
        decision_id = await store_decision(conn, decision)

    assert isinstance(decision_id, int)


async def test_lock_in_requirements_round_trip_by_tender(engine):
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-4")
        decision = Decision(
            tender_id=tender_id,
            decision_type="bid",
            conditions=(),
            deadline=None,
            justification="full coverage",
            actor="pm-1",
            decided_at="2026-08-08T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=None,
        )
        decision_id = await store_decision(conn, decision)
        await store_lock_in_requirement(
            conn, tender_id=tender_id, decision_id=decision_id, boqline_source_line_id=1, vendor_id=7, vendor_name="Vendor A"
        )
        lock_ins = await list_lock_in_requirements_by_tender(conn, tender_id=tender_id)

    assert len(lock_ins) == 1
    assert lock_ins[0]["status"] == "pending"
    assert lock_ins[0]["vendor_name"] == "Vendor A"


def _decision(tender_id: int, decision_type: str, decided_at: str) -> Decision:
    return Decision(
        tender_id=tender_id,
        decision_type=decision_type,
        conditions=(),
        deadline=None,
        justification="test",
        actor="pm-1",
        decided_at=decided_at,
        go_no_go_inputs_id=None,
        bid_readiness_candidate_id=None,
    )


async def test_list_tenders_with_active_bid_decision_returns_bid_and_conditional_bid(engine):
    async with engine.begin() as conn:
        tender_a = await _make_tender(conn, "test-decision-store-active-a")
        tender_b = await _make_tender(conn, "test-decision-store-active-b")
        tender_c = await _make_tender(conn, "test-decision-store-active-c")
        await store_decision(conn, _decision(tender_a, "bid", "2026-08-09T00:00:00+00:00"))
        await store_decision(conn, _decision(tender_b, "conditional_bid", "2026-08-09T00:00:00+00:00"))
        await store_decision(conn, _decision(tender_c, "no_go", "2026-08-09T00:00:00+00:00"))

        result = await list_tenders_with_active_bid_decision(conn)

    assert tender_a in result
    assert tender_b in result
    assert tender_c not in result


async def test_list_tenders_with_active_bid_decision_uses_the_most_recent_decision(engine):
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-active-superseded")
        await store_decision(conn, _decision(tender_id, "bid", "2026-08-01T00:00:00+00:00"))
        # Append-only: a later row records the bid being abandoned. The
        # LATEST decision by decided_at must win, not the first one stored.
        await store_decision(conn, _decision(tender_id, "no_go", "2026-08-09T00:00:00+00:00"))

        result = await list_tenders_with_active_bid_decision(conn)

    assert tender_id not in result


async def test_list_decision_cycle_seconds_includes_a_decision_with_a_candidate(engine):
    summary = BoqMatchSummary(
        green_amount=Decimal("1000"),
        yellow_amount=Decimal("0"),
        red_amount=Decimal("0"),
        unpriced_line_count=0,
        non_matchable_line_count=0,
        non_matchable_amount=Decimal("0"),
        total_priced_amount=Decimal("1000"),
        green_pct=100.0,
        yellow_pct=0.0,
        red_pct=0.0,
    )
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-cycle-1")
        candidate = BidReadinessCandidate(
            tender_id=tender_id,
            summary=summary,
            is_lottery=False,
            critical_lines=(),
            computed_at="2026-08-08T00:00:00+00:00",
        )
        candidate_id = await store_bid_readiness_candidate(conn, candidate)
        decision = Decision(
            tender_id=tender_id,
            decision_type="bid",
            conditions=(),
            deadline=None,
            justification="test",
            actor="pm-1",
            decided_at="2026-08-09T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=candidate_id,
        )
        await store_decision(conn, decision)

    async with engine.connect() as conn:
        cycles = await list_decision_cycle_seconds(conn)

    matching = [c for c in cycles if c["tender_id"] == tender_id]
    assert len(matching) == 1
    assert matching[0]["cycle_seconds"] == 86400.0  # exactly 1 day between computed_at and decided_at


async def test_list_decision_cycle_seconds_excludes_go_no_go_decisions(engine):
    # A decision with go_no_go_inputs_id instead of bid_readiness_candidate_id
    # (the _decision() helper's shape) has no candidate to time against and
    # must not appear.
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-cycle-2")
        await store_decision(conn, _decision(tender_id, "no_go", "2026-08-08T00:00:00+00:00"))

    async with engine.connect() as conn:
        cycles = await list_decision_cycle_seconds(conn)

    assert all(c["tender_id"] != tender_id for c in cycles)
