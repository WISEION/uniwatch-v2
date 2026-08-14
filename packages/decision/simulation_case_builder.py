"""Converts already-real decision-layer facts into the generic
`SimulationCase` shape `packages/algorithm`'s simulation engine consumes
(Phase 5, task 5.C, docs/reports/PLAN-MISSION-5.md Section3 task 5.C row 1
-- "synthetic vendor cases"/"frozen real tender snapshots"/"historical
outcomes"). Lives in `packages/decision`, not `packages/algorithm`, because
`packages/algorithm` "does not own business facts" (AGENTS.md Section3) --
it must stay ignorant of what a BOQ line or a vendor offer is.

`build_case_from_bid_readiness` serves BOTH the "synthetic vendor cases"
and "frozen real tender snapshots" bullets -- the distinction is purely
which BoqLine/offer data the *caller* built the `BidReadinessCandidate`
from (a real frozen fixture's BOQ lines vs a hand-built synthetic set);
vendor offers are always synthetic today regardless (ADR-0004), so the
"synthetic vendor" vs "frozen real tender" split lives in which BOQ
dataset was used, not in this function. The caller picks the
`case_source` label when recording the run
(packages/algorithm/simulation_store.record_simulation_run).

Every numeric field copied here is one `packages/decision`'s own task 4.A
(`bid_readiness.py`) or task 4.D (`calibration_model.py`) already computed
or a human already entered for a real reason -- nothing here derives a new
number. A source field that is `None` (e.g. `TenderOutcome.
our_submitted_amount` when a human never recorded one) propagates as
`None`, never defaulted to `0` (AGENTS.md hard ban #3)."""

from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from packages.algorithm.simulation_engine import SimulationCase
from packages.decision.bid_readiness import BidReadinessCandidate


def _parse_decimal(value: str | None) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(value)
    except InvalidOperation:
        return None


def build_case_from_bid_readiness(
    candidate: BidReadinessCandidate,
    *,
    case_id: str,
    monetary_currency: str | None = None,
    actual_outcome_label: str | None = None,
    human_overrides: dict[str, str] | None = None,
) -> SimulationCase:
    summary = candidate.summary
    inputs: dict[str, Any] = {
        "coverage_pct": summary.green_pct + summary.yellow_pct,
        "green_pct": summary.green_pct,
        "yellow_pct": summary.yellow_pct,
        "red_pct": summary.red_pct,
        "is_lottery": candidate.is_lottery,
        "critical_line_count": len(candidate.critical_lines),
        "unpriced_line_count": summary.unpriced_line_count,
        "non_matchable_line_count": summary.non_matchable_line_count,
    }
    return SimulationCase(
        case_id=case_id,
        inputs=inputs,
        human_overrides=human_overrides or {},
        monetary_amount=summary.total_priced_amount,
        monetary_currency=monetary_currency,
        actual_outcome_label=actual_outcome_label,
    )


def build_case_from_tender_outcome(
    outcome: dict[str, Any],
    *,
    case_id: str,
    human_overrides: dict[str, str] | None = None,
) -> SimulationCase:
    """`outcome` is the dict shape
    `packages/decision/calibration_store.load_tender_outcome`/
    `list_outcomes_by_organization_voen` already return -- this function
    does not fetch or shape that data itself, only translates it."""
    monetary_amount = _parse_decimal(outcome.get("our_submitted_amount"))
    return SimulationCase(
        case_id=case_id,
        inputs={"outcome": outcome["outcome"]},
        human_overrides=human_overrides or {},
        monetary_amount=monetary_amount,
        monetary_currency=outcome.get("currency") if monetary_amount is not None else None,
        actual_outcome_label=outcome["outcome"],
    )
