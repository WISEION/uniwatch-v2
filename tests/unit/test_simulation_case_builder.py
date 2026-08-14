"""Unit tests for packages/decision/simulation_case_builder.py (Phase 5,
task 5.C) -- converting already-real decision-layer facts into the generic
SimulationCase shape packages/algorithm's engine consumes."""

from __future__ import annotations

from decimal import Decimal

from packages.decision.bid_readiness import BidReadinessCandidate, CriticalLine
from packages.decision.boq_summary import BoqMatchSummary
from packages.decision.simulation_case_builder import (
    build_case_from_bid_readiness,
    build_case_from_tender_outcome,
)


def _summary(**overrides) -> BoqMatchSummary:
    base = {
        "green_amount": Decimal("700"),
        "yellow_amount": Decimal("200"),
        "red_amount": Decimal("100"),
        "unpriced_line_count": 1,
        "non_matchable_line_count": 2,
        "non_matchable_amount": Decimal("50"),
        "total_priced_amount": Decimal("1000"),
        "green_pct": 70.0,
        "yellow_pct": 20.0,
        "red_pct": 10.0,
    }
    base.update(overrides)
    return BoqMatchSummary(**base)


def test_build_case_from_bid_readiness_copies_real_computed_fields():
    candidate = BidReadinessCandidate(
        tender_id=355920,
        summary=_summary(),
        is_lottery=True,
        critical_lines=(CriticalLine(boqline_source_line_id=1, vendor_id=42, vendor_name="Acme"),),
        computed_at="2026-08-14T00:00:00Z",
    )
    case = build_case_from_bid_readiness(candidate, case_id="tender-355920", monetary_currency="AZN")

    assert case.case_id == "tender-355920"
    assert case.inputs["coverage_pct"] == 90.0
    assert case.inputs["is_lottery"] is True
    assert case.inputs["critical_line_count"] == 1
    assert case.inputs["unpriced_line_count"] == 1
    assert case.inputs["non_matchable_line_count"] == 2
    assert case.monetary_amount == Decimal("1000")
    assert case.monetary_currency == "AZN"
    assert case.actual_outcome_label is None


def test_build_case_from_bid_readiness_passes_through_human_overrides():
    candidate = BidReadinessCandidate(
        tender_id=1,
        summary=_summary(),
        is_lottery=False,
        critical_lines=(),
        computed_at="2026-08-14T00:00:00Z",
    )
    case = build_case_from_bid_readiness(candidate, case_id="t1", human_overrides={"bid_gate": "approve"})
    assert case.human_overrides == {"bid_gate": "approve"}


def test_build_case_from_tender_outcome_propagates_none_amount_faithfully():
    outcome = {
        "outcome": "lost",
        "our_submitted_amount": None,
        "winner_amount": "950000",
        "currency": "AZN",
    }
    case = build_case_from_tender_outcome(outcome, case_id="t2")
    assert case.monetary_amount is None
    assert case.monetary_currency is None  # never guessed from winner_amount's currency
    assert case.actual_outcome_label == "lost"
    assert case.inputs == {"outcome": "lost"}


def test_build_case_from_tender_outcome_copies_our_submitted_amount_and_currency():
    outcome = {
        "outcome": "won",
        "our_submitted_amount": "500000.50",
        "winner_amount": "500000.50",
        "currency": "USD",
    }
    case = build_case_from_tender_outcome(outcome, case_id="t3")
    assert case.monetary_amount == Decimal("500000.50")
    assert case.monetary_currency == "USD"
    assert case.actual_outcome_label == "won"
