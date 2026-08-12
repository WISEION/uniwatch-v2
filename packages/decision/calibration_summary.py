"""Calibration comparison arithmetic (Phase 4, task 4.D,
TENDER_INTELLIGENCE_SPEC.md Section7.4, P319: "цена победителя vs своя
оценка рыночной себестоимости -> где база SCG врёт"). Pure functions, no
DB, no network -- same shape as execution_ledger_summary.py.

No formula is invented here: winner_amount and our_submitted_amount are
human-entered facts (calibration_model.py), and our_scg_cost_basis is
arithmetic the caller derives from packages/decision/matching.py's already
-computed TCO ranking (real vendor offers) -- this module only subtracts.

The one thing this module actively guards against: BOQ coverage is partial
by design (bid_readiness.py's ~85% threshold exists precisely because full
coverage is not the norm). Comparing a partial cost sum against a
whole-tender winner price would produce a number that looks like a margin
and is actually an artifact of missing coverage. `PriceComparison` always
carries `coverage_line_count`/`total_line_count`/`is_partial_coverage`
alongside every delta -- hard ban #3 applied to arithmetic, not just to
missing facts.

Deliberately NOT produced here: any verdict about which of Section7.4's
three loss diagnoses (vendor gap / dumping / drawn tender) explains a given
delta -- the spec supplies no rule for choosing between them from the delta
alone; a human reads the delta plus the recorded loss reasons and
concludes."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any


@dataclass(frozen=True)
class PriceComparison:
    winner_amount: Decimal | None
    our_submitted_amount: Decimal | None
    our_scg_cost_basis: Decimal | None
    winner_vs_our_submitted: Decimal | None
    winner_vs_our_cost_basis: Decimal | None
    coverage_line_count: int
    total_line_count: int
    is_partial_coverage: bool


def compare_winner_to_our_basis(
    *,
    winner_amount: Decimal | None,
    our_submitted_amount: Decimal | None,
    our_scg_cost_basis: Decimal | None,
    priced_line_count: int,
    total_line_count: int,
) -> PriceComparison:
    return PriceComparison(
        winner_amount=winner_amount,
        our_submitted_amount=our_submitted_amount,
        our_scg_cost_basis=our_scg_cost_basis,
        # Hard ban #3: a missing operand yields a missing delta, never a
        # delta computed against a guessed zero.
        winner_vs_our_submitted=(
            winner_amount - our_submitted_amount if winner_amount is not None and our_submitted_amount is not None else None
        ),
        winner_vs_our_cost_basis=(
            winner_amount - our_scg_cost_basis if winner_amount is not None and our_scg_cost_basis is not None else None
        ),
        coverage_line_count=priced_line_count,
        total_line_count=total_line_count,
        is_partial_coverage=priced_line_count < total_line_count,
    )


def summarize_loss_reasons(rows: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for row in rows:
        counts[row["loss_reason"]] = counts.get(row["loss_reason"], 0) + 1
    return counts
