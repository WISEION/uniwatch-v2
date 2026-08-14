"""Persistence for АЛГОРИТМ simulation/backtest runs (Phase 5, task 5.C,
docs/reports/PLAN-MISSION-5.md Section3 / master plan Section14.5's own
"algorithm_simulation_runs" name).

A run row is itself immutable historical evidence -- there is no
update/delete function here, same discipline policy_nodes/policy_edges
already use in policy_store.py: what a version did against a given case
set at a given time does not get edited after the fact.

Two kinds of run share one table (case_traces distinguishes them via a
"kind" marker inside each stored element, not a schema split):
record_simulation_run() stores per-case CaseTrace results (kind="trace");
record_comparison_run() stores per-case VersionComparison results
(kind="comparison", case_source is always "mixed"). A comparison run's
completed/awaiting_human/undetermined counts are not meaningful (a
comparison is agree/disagree, not a single-version walk outcome) -- they
are stored as 0, not a fabricated business number, and the real signal
lives in terminal_distribution's own {"agree": N, "disagree": M} shape for
that case.

list_case_traces() is the review-queue/human-override-rate surface:
per this task's own recorded reading (docs/decisions/OPEN-QUESTIONS.md),
deciding whether a simulated result "agrees" with a case's
actual_outcome_label would require inventing a correspondence between
free-text reason codes and free-text outcome labels no source document
supplies. This function returns both, side by side, unclassified -- the
same "arithmetic gives a delta, a human makes the call" precedent
packages/decision/calibration_summary.py already established."""

from __future__ import annotations

import json
from collections import Counter
from decimal import Decimal
from statistics import median
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .simulation_engine import CaseTrace, SimulationCase, VersionComparison

_JSON_COLUMNS = ("terminal_distribution", "reason_code_distribution", "subgroup_distribution", "monetary_range", "case_traces")


def _trace_to_dict(trace: CaseTrace) -> dict[str, Any]:
    return {
        "kind": "trace",
        "case_id": trace.case_id,
        "status": trace.status,
        "path": list(trace.path),
        "terminal_node_key": trace.terminal_node_key,
        "reason_codes": list(trace.reason_codes),
        "undetermined_reason": trace.undetermined_reason,
        "final_state": trace.final_state,
        "monetary_amount": str(trace.monetary_amount) if trace.monetary_amount is not None else None,
        "monetary_currency": trace.monetary_currency,
        "actual_outcome_label": trace.actual_outcome_label,
    }


def _comparison_to_dict(comparison: VersionComparison) -> dict[str, Any]:
    return {
        "kind": "comparison",
        "case_id": comparison.case_id,
        "terminal_a": comparison.terminal_a,
        "terminal_b": comparison.terminal_b,
        "reason_codes_a": list(comparison.reason_codes_a),
        "reason_codes_b": list(comparison.reason_codes_b),
        "agrees": comparison.agrees,
    }


def _terminal_distribution(traces: tuple[CaseTrace, ...]) -> dict[str, int]:
    return dict(Counter(t.terminal_node_key for t in traces if t.terminal_node_key is not None))


def _reason_code_distribution(traces: tuple[CaseTrace, ...]) -> dict[str, int]:
    counts: Counter[str] = Counter()
    for t in traces:
        counts.update(t.reason_codes)
    return dict(counts)


def _monetary_range(traces: tuple[CaseTrace, ...]) -> tuple[dict[str, Any] | None, int]:
    """Grouped by (terminal_node_key, currency) -- never summed across
    currencies (D-TAX; same discipline packages/decision/matching.py
    already applies to cross-currency vendor offers). A monetary_amount
    with no declared currency is excluded from every range and counted
    separately, not silently mixed into any group."""
    groups: dict[tuple[str, str], list[Decimal]] = {}
    uncurrencied = 0
    for t in traces:
        if t.monetary_amount is None:
            continue
        if t.monetary_currency is None:
            uncurrencied += 1
            continue
        key = (t.terminal_node_key or "__no_terminal__", t.monetary_currency)
        groups.setdefault(key, []).append(t.monetary_amount)
    if not groups:
        return None, uncurrencied
    result = {
        f"{terminal}::{currency}": {
            "min": str(min(amounts)),
            "max": str(max(amounts)),
            "median": str(median(amounts)),
            "count": len(amounts),
        }
        for (terminal, currency), amounts in groups.items()
    }
    return result, uncurrencied


def _subgroup_distribution(
    traces: tuple[CaseTrace, ...], cases_by_id: dict[str, SimulationCase], subgroup_by: str
) -> dict[str, dict[str, int]]:
    groups: dict[str, Counter[str]] = {}
    for t in traces:
        case = cases_by_id.get(t.case_id)
        group_key = str(case.inputs.get(subgroup_by)) if case is not None else "__unknown_case__"
        groups.setdefault(group_key, Counter())[t.terminal_node_key or "__none__"] += 1
    return {group_key: dict(counts) for group_key, counts in groups.items()}


def _deserialize_run(row: dict[str, Any]) -> dict[str, Any]:
    for key in _JSON_COLUMNS:
        if isinstance(row.get(key), str):
            row[key] = json.loads(row[key])
    return row


async def record_simulation_run(
    conn: AsyncConnection,
    *,
    policy_version_id: int,
    case_set_label: str,
    case_source: str,
    traces: tuple[CaseTrace, ...],
    run_by: str,
    cases: list[SimulationCase] | None = None,
    subgroup_by: str | None = None,
    notes: str | None = None,
) -> int:
    subgroup = None
    if subgroup_by is not None and cases is not None:
        subgroup = _subgroup_distribution(traces, {c.case_id: c for c in cases}, subgroup_by)
    monetary_range, uncurrencied = _monetary_range(traces)

    return (
        await conn.execute(
            text(
                """
                INSERT INTO algorithm_simulation_runs
                    (policy_version_id, case_set_label, case_source, case_count, completed_count,
                     awaiting_human_count, undetermined_count, terminal_distribution,
                     reason_code_distribution, subgroup_distribution, monetary_range,
                     monetary_amount_uncurrencied_count, case_traces, run_by, notes)
                VALUES
                    (:policy_version_id, :case_set_label, :case_source, :case_count, :completed_count,
                     :awaiting_human_count, :undetermined_count, CAST(:terminal_distribution AS jsonb),
                     CAST(:reason_code_distribution AS jsonb), CAST(:subgroup_distribution AS jsonb),
                     CAST(:monetary_range AS jsonb), :monetary_amount_uncurrencied_count,
                     CAST(:case_traces AS jsonb), :run_by, :notes)
                RETURNING id
                """
            ),
            {
                "policy_version_id": policy_version_id,
                "case_set_label": case_set_label,
                "case_source": case_source,
                "case_count": len(traces),
                "completed_count": sum(1 for t in traces if t.status == "completed"),
                "awaiting_human_count": sum(1 for t in traces if t.status == "awaiting_human"),
                "undetermined_count": sum(1 for t in traces if t.status == "undetermined"),
                "terminal_distribution": json.dumps(_terminal_distribution(traces)),
                "reason_code_distribution": json.dumps(_reason_code_distribution(traces)),
                "subgroup_distribution": json.dumps(subgroup) if subgroup is not None else None,
                "monetary_range": json.dumps(monetary_range) if monetary_range is not None else None,
                "monetary_amount_uncurrencied_count": uncurrencied,
                "case_traces": json.dumps([_trace_to_dict(t) for t in traces]),
                "run_by": run_by,
                "notes": notes,
            },
        )
    ).scalar_one()


async def record_comparison_run(
    conn: AsyncConnection,
    *,
    policy_version_id: int,
    compared_against_version_id: int,
    case_set_label: str,
    comparisons: tuple[VersionComparison, ...],
    run_by: str,
    notes: str | None = None,
) -> int:
    agree_count = sum(1 for c in comparisons if c.agrees)
    terminal_distribution = {"agree": agree_count, "disagree": len(comparisons) - agree_count}

    return (
        await conn.execute(
            text(
                """
                INSERT INTO algorithm_simulation_runs
                    (policy_version_id, compared_against_version_id, case_set_label, case_source,
                     case_count, completed_count, awaiting_human_count, undetermined_count,
                     terminal_distribution, reason_code_distribution, case_traces, run_by, notes)
                VALUES
                    (:policy_version_id, :compared_against_version_id, :case_set_label, 'mixed',
                     :case_count, 0, 0, 0, CAST(:terminal_distribution AS jsonb),
                     CAST(:reason_code_distribution AS jsonb), CAST(:case_traces AS jsonb), :run_by, :notes)
                RETURNING id
                """
            ),
            {
                "policy_version_id": policy_version_id,
                "compared_against_version_id": compared_against_version_id,
                "case_set_label": case_set_label,
                "case_count": len(comparisons),
                "terminal_distribution": json.dumps(terminal_distribution),
                "reason_code_distribution": json.dumps({}),
                "case_traces": json.dumps([_comparison_to_dict(c) for c in comparisons]),
                "run_by": run_by,
                "notes": notes,
            },
        )
    ).scalar_one()


async def get_simulation_run(conn: AsyncConnection, *, run_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_version_id, compared_against_version_id, case_set_label, case_source,
                           case_count, completed_count, awaiting_human_count, undetermined_count,
                           terminal_distribution, reason_code_distribution, subgroup_distribution,
                           monetary_range, monetary_amount_uncurrencied_count, case_traces, run_by,
                           run_at, notes
                    FROM algorithm_simulation_runs WHERE id = :id
                    """
                ),
                {"id": run_id},
            )
        )
        .mappings()
        .first()
    )
    return _deserialize_run(dict(row)) if row is not None else None


async def list_simulation_runs_by_version(conn: AsyncConnection, *, policy_version_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_version_id, compared_against_version_id, case_set_label, case_source,
                           case_count, completed_count, awaiting_human_count, undetermined_count,
                           terminal_distribution, reason_code_distribution, subgroup_distribution,
                           monetary_range, monetary_amount_uncurrencied_count, case_traces, run_by,
                           run_at, notes
                    FROM algorithm_simulation_runs WHERE policy_version_id = :policy_version_id ORDER BY run_at
                    """
                ),
                {"policy_version_id": policy_version_id},
            )
        )
        .mappings()
        .all()
    )
    return [_deserialize_run(dict(row)) for row in rows]


async def list_case_traces(conn: AsyncConnection, *, run_id: int) -> list[dict[str, Any]]:
    run = await get_simulation_run(conn, run_id=run_id)
    if run is None:
        return []
    traces = run["case_traces"]
    return list(traces) if isinstance(traces, list) else []
