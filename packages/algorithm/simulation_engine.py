"""АЛГОРИТМ simulation/backtest engine (Phase 5, task 5.C,
docs/reports/PLAN-MISSION-5.md Section3 / master plan Section12.7). Pure
functions, no DB -- packages/algorithm/simulation_store.py persists results.

The fundamental fact this module works around: no PolicyNode carries
executable logic. There is no formula, decision table, or weight anywhere
in this schema (5.A left test_cases opaque JSON on purpose; 5.B only added
the covers_condition convention for branch-coverage bookkeeping). Building
an engine that evaluates a real formula would require inventing one --
forbidden by AGENTS.md hard ban #2 and D-FIN/TBD-04. So this is a
test-case-REPLAY engine, not a formula executor: at a branch point, a
node's real behavior for a given case is whichever of its own
human-authored test_cases the case's current state matches -- the
human-declared example IS the decision table.

This wires up test_cases' existing "input"/"expected_output" scaffolding
(already present, unused, in 5.B's own test fixtures --
tests/unit/test_policy_validator.py's
{"input": {}, "expected_output": {}, "covers_condition": ...}) rather than
inventing a new key. A running `state` dict (seeded from
SimulationCase.inputs) accumulates each matched test case's
expected_output as the walk proceeds, so a downstream node's input match
can depend on an upstream node's declared output -- the same
producer/consumer relationship policy_validator's io_type_mismatch check
already validates structurally between adjacent nodes' contracts.

Nothing here is ever guessed. A branch with zero or ambiguous (2+ distinct
covers_condition) matching test cases is `undetermined`, never defaulted to
any particular edge (AGENTS.md hard ban #3). A Human node with neither a
case-supplied override nor a matching test case is `awaiting_human`, not
auto-decided -- an engine cannot stand in for a person, only replay what a
human declared (in test_cases) or already said (in human_overrides, which
is how a historical, already-decided real case gets simulated at all)."""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

NodeDict = dict[str, Any]
EdgeDict = dict[str, Any]

_UNDETERMINED = "undetermined"
_AWAITING_HUMAN = "awaiting_human"
_COMPLETED = "completed"


@dataclass(frozen=True)
class SimulationCase:
    case_id: str
    inputs: dict[str, Any]
    human_overrides: dict[str, str] = field(default_factory=dict)
    monetary_amount: Decimal | None = None
    monetary_currency: str | None = None
    actual_outcome_label: str | None = None


@dataclass(frozen=True)
class CaseTrace:
    case_id: str
    status: str
    path: tuple[str, ...]
    terminal_node_key: str | None
    reason_codes: tuple[str, ...]
    undetermined_reason: str | None
    final_state: dict[str, Any]
    monetary_amount: Decimal | None
    monetary_currency: str | None
    actual_outcome_label: str | None


@dataclass(frozen=True)
class VersionComparison:
    case_id: str
    terminal_a: str | None
    terminal_b: str | None
    reason_codes_a: tuple[str, ...]
    reason_codes_b: tuple[str, ...]
    agrees: bool


def _build_out_adjacency(nodes: list[NodeDict], edges: list[EdgeDict]) -> dict[str, list[EdgeDict]]:
    out_adj: dict[str, list[EdgeDict]] = {n["node_key"]: [] for n in nodes}
    for edge in edges:
        out_adj.setdefault(edge["from_node_key"], []).append(edge)
    return out_adj


def _find_start_node(nodes: list[NodeDict], edges: list[EdgeDict]) -> str:
    """Same incoming-adjacency notion policy_validator._build_adjacency uses,
    including fallback_node_key as an implicit edge. Requires exactly one
    such node -- run_case/run_simulation assume an already-validate_graph-
    clean input, the same precondition policy_store.submit_for_approval
    enforces before a version may progress past risk_review."""
    node_keys = {n["node_key"] for n in nodes}
    incoming: dict[str, int] = dict.fromkeys(node_keys, 0)
    for edge in edges:
        if edge["to_node_key"] in incoming:
            incoming[edge["to_node_key"]] += 1
    for node in nodes:
        fallback = node.get("fallback_node_key")
        if fallback is not None and fallback in incoming:
            incoming[fallback] += 1
    starts = [k for k, count in incoming.items() if count == 0]
    if len(starts) != 1:
        raise ValueError(
            f"simulation requires exactly one start node (found {len(starts)}); run policy_validator.validate_graph first"
        )
    return starts[0]


def _input_matches(test_case_input: dict[str, Any], state: dict[str, Any]) -> bool:
    return all(key in state and state[key] == value for key, value in test_case_input.items())


def _matching_test_cases(node: NodeDict, state: dict[str, Any]) -> list[dict[str, Any]]:
    matches = []
    for tc in node.get("test_cases") or ():
        if not isinstance(tc, dict):
            continue
        tc_input = tc.get("input")
        if isinstance(tc_input, dict) and _input_matches(tc_input, state):
            matches.append(tc)
    return matches


def _select_next_edge(
    node: NodeDict,
    outgoing: list[EdgeDict],
    state: dict[str, Any],
    human_overrides: dict[str, str],
) -> tuple[EdgeDict | None, str | None, dict[str, Any] | None]:
    """Returns (chosen_edge, undetermined_reason, expected_output_to_merge).
    undetermined_reason is "awaiting_human" for the one non-error stop
    condition (a Human node genuinely waiting on a person), or one of this
    task's own error codes otherwise. Priority: deterministic single
    unconditional edge > human override > test-case replay."""
    if len(outgoing) == 1 and outgoing[0].get("condition_label") is None:
        matches = _matching_test_cases(node, state)
        expected_output = matches[0].get("expected_output") if len(matches) == 1 else None
        return outgoing[0], None, expected_output

    node_key = node["node_key"]
    if node.get("node_type") == "human" and node_key in human_overrides:
        chosen_label = human_overrides[node_key]
        matched = [e for e in outgoing if e.get("condition_label") == chosen_label]
        if not matched:
            return None, "human_override_no_matching_edge", None
        return matched[0], None, None

    matches = _matching_test_cases(node, state)
    distinct_labels = {tc.get("covers_condition") for tc in matches}
    if not distinct_labels:
        if node.get("node_type") == "human":
            return None, _AWAITING_HUMAN, None
        return None, "no_matching_test_case", None
    if len(distinct_labels) > 1:
        return None, "ambiguous_test_cases", None

    label = distinct_labels.pop()
    matched_edges = [e for e in outgoing if e.get("condition_label") == label]
    if not matched_edges:
        return None, "test_case_covers_unknown_edge", None
    winning_test_case = next(tc for tc in matches if tc.get("covers_condition") == label)
    return matched_edges[0], None, winning_test_case.get("expected_output")


def run_case(nodes: list[NodeDict], edges: list[EdgeDict], case: SimulationCase) -> CaseTrace:
    node_by_key = {n["node_key"]: n for n in nodes}
    out_adj = _build_out_adjacency(nodes, edges)
    current = _find_start_node(nodes, edges)
    state = dict(case.inputs)
    path = [current]
    step_cap = max(len(nodes) * 2, 1)

    for _ in range(step_cap):
        node = node_by_key[current]
        outgoing = out_adj.get(current, [])
        if not outgoing:
            return CaseTrace(
                case_id=case.case_id,
                status=_COMPLETED,
                path=tuple(path),
                terminal_node_key=current,
                reason_codes=tuple(node.get("reason_codes") or ()),
                undetermined_reason=None,
                final_state=state,
                monetary_amount=case.monetary_amount,
                monetary_currency=case.monetary_currency,
                actual_outcome_label=case.actual_outcome_label,
            )

        edge, reason, expected_output = _select_next_edge(node, outgoing, state, case.human_overrides)
        if edge is None:
            status = _AWAITING_HUMAN if reason == _AWAITING_HUMAN else _UNDETERMINED
            return CaseTrace(
                case_id=case.case_id,
                status=status,
                path=tuple(path),
                terminal_node_key=None,
                reason_codes=(),
                undetermined_reason=reason,
                final_state=state,
                monetary_amount=case.monetary_amount,
                monetary_currency=case.monetary_currency,
                actual_outcome_label=case.actual_outcome_label,
            )

        if isinstance(expected_output, dict):
            state = {**state, **expected_output}
        current = edge["to_node_key"]
        path.append(current)

    return CaseTrace(
        case_id=case.case_id,
        status=_UNDETERMINED,
        path=tuple(path),
        terminal_node_key=None,
        reason_codes=(),
        undetermined_reason="step_limit_exceeded",
        final_state=state,
        monetary_amount=case.monetary_amount,
        monetary_currency=case.monetary_currency,
        actual_outcome_label=case.actual_outcome_label,
    )


def run_simulation(nodes: list[NodeDict], edges: list[EdgeDict], cases: list[SimulationCase]) -> tuple[CaseTrace, ...]:
    return tuple(run_case(nodes, edges, case) for case in cases)


def compare_versions(
    nodes_a: list[NodeDict],
    edges_a: list[EdgeDict],
    nodes_b: list[NodeDict],
    edges_b: list[EdgeDict],
    cases: list[SimulationCase],
) -> tuple[VersionComparison, ...]:
    traces_a = {t.case_id: t for t in run_simulation(nodes_a, edges_a, cases)}
    traces_b = {t.case_id: t for t in run_simulation(nodes_b, edges_b, cases)}
    comparisons = []
    for case in cases:
        trace_a = traces_a[case.case_id]
        trace_b = traces_b[case.case_id]
        agrees = trace_a.terminal_node_key == trace_b.terminal_node_key and trace_a.reason_codes == trace_b.reason_codes
        comparisons.append(
            VersionComparison(
                case_id=case.case_id,
                terminal_a=trace_a.terminal_node_key,
                terminal_b=trace_b.terminal_node_key,
                reason_codes_a=trace_a.reason_codes,
                reason_codes_b=trace_b.reason_codes,
                agrees=agrees,
            )
        )
    return tuple(comparisons)
