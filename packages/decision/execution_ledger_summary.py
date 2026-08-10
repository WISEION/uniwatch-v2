"""Pure plan/fact rollup for one tender's ExecutionFacts (Phase 4, task
4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3, P318's "дельта план/факт по
строкам" and "вклад в исторический буфер накладных"). No DB access -- the
route/job that calls this already has the fact list from
execution_ledger_store.list_execution_facts_by_tender."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .execution_fact_model import DEVIATION_CATEGORIES


@dataclass(frozen=True)
class PlanFactDelta:
    boqline_source_line_id: int
    planned_qty: Decimal
    actual_qty: Decimal
    delta: Decimal


def summarize_plan_fact_deltas(facts: list[dict[str, Any]]) -> tuple[PlanFactDelta, ...]:
    deltas = [
        PlanFactDelta(
            boqline_source_line_id=f["boqline_source_line_id"],
            planned_qty=f["planned_qty"],
            actual_qty=f["actual_qty"],
            delta=f["actual_qty"] - f["planned_qty"],
        )
        for f in facts
        if f["boqline_source_line_id"] is not None and f["planned_qty"] is not None and f["actual_qty"] is not None
    ]
    return tuple(sorted(deltas, key=lambda d: d.boqline_source_line_id))


def summarize_deviation_category_counts(facts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in facts:
        category = f["deviation_category"]
        if category is None:
            continue
        assert category in DEVIATION_CATEGORIES
        counts[category] = counts.get(category, 0) + 1
    return counts
