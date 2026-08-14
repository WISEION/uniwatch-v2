"""Unit tests for the АЛГОРИТМ simulation/backtest engine (Phase 5, task
5.C). Test-case-replay semantics: a node's behavior at a branch point is
whichever of its own test_cases' "input" dict matches the running state."""

from __future__ import annotations

from decimal import Decimal

from packages.algorithm.simulation_engine import (
    SimulationCase,
    compare_versions,
    run_case,
    run_simulation,
)


def _node(node_key: str, node_type: str = "gate", **overrides) -> dict:
    base = {
        "node_key": node_key,
        "node_type": node_type,
        "test_cases": (),
        "reason_codes": (),
        "fallback_node_key": None,
    }
    base.update(overrides)
    return base


def _edge(from_node_key: str, to_node_key: str, condition_label: str | None = None) -> dict:
    return {"from_node_key": from_node_key, "to_node_key": to_node_key, "condition_label": condition_label}


def _case(case_id: str, **overrides) -> SimulationCase:
    return SimulationCase(case_id=case_id, inputs=overrides.pop("inputs", {}), **overrides)


def test_linear_graph_walks_straight_through_to_terminal():
    nodes = [_node("start"), _node("end", reason_codes=("ok",))]
    edges = [_edge("start", "end")]
    trace = run_case(nodes, edges, _case("c1"))
    assert trace.status == "completed"
    assert trace.path == ("start", "end")
    assert trace.terminal_node_key == "end"
    assert trace.reason_codes == ("ok",)


def test_rule_node_routes_two_cases_down_two_different_edges():
    nodes = [
        _node("start"),
        _node(
            "r",
            node_type="rule",
            test_cases=(
                {"input": {"amount": 100}, "expected_output": {}, "covers_condition": "low"},
                {"input": {"amount": 900}, "expected_output": {}, "covers_condition": "high"},
            ),
        ),
        _node("low_path", reason_codes=("low_value",)),
        _node("high_path", reason_codes=("high_value",)),
    ]
    edges = [_edge("start", "r"), _edge("r", "low_path", "low"), _edge("r", "high_path", "high")]

    low_trace = run_case(nodes, edges, _case("low1", inputs={"amount": 100}))
    high_trace = run_case(nodes, edges, _case("high1", inputs={"amount": 900}))

    assert low_trace.terminal_node_key == "low_path"
    assert high_trace.terminal_node_key == "high_path"


def test_expected_output_propagates_into_downstream_matching():
    nodes = [
        _node("start"),
        _node(
            "r",
            node_type="rule",
            test_cases=({"input": {}, "expected_output": {"tier": "gold"}, "covers_condition": "any"},),
        ),
        _node(
            "gate",
            node_type="gate",
            test_cases=({"input": {"tier": "gold"}, "expected_output": {}, "covers_condition": "approve"},),
        ),
        _node("approved", reason_codes=("approved",)),
        _node("rejected", reason_codes=("rejected",)),
    ]
    edges = [
        _edge("start", "r"),
        _edge("r", "gate", "any"),
        _edge("gate", "approved", "approve"),
        _edge("gate", "rejected", "deny"),
    ]
    trace = run_case(nodes, edges, _case("c1"))
    assert trace.terminal_node_key == "approved"
    assert trace.final_state["tier"] == "gold"


def test_no_matching_test_case_is_undetermined_not_guessed():
    nodes = [
        _node("start"),
        _node(
            "r",
            node_type="rule",
            test_cases=({"input": {"amount": 100}, "expected_output": {}, "covers_condition": "low"},),
        ),
        _node("low_path"),
        _node("high_path"),
    ]
    edges = [_edge("start", "r"), _edge("r", "low_path", "low"), _edge("r", "high_path", "high")]
    trace = run_case(nodes, edges, _case("c1", inputs={"amount": 5000}))
    assert trace.status == "undetermined"
    assert trace.undetermined_reason == "no_matching_test_case"
    assert trace.terminal_node_key is None


def test_ambiguous_test_cases_is_undetermined():
    nodes = [
        _node("start"),
        _node(
            "r",
            node_type="rule",
            test_cases=(
                {"input": {"region": "baku"}, "expected_output": {}, "covers_condition": "low"},
                {"input": {"amount": 100}, "expected_output": {}, "covers_condition": "high"},
            ),
        ),
        _node("low_path"),
        _node("high_path"),
    ]
    edges = [_edge("start", "r"), _edge("r", "low_path", "low"), _edge("r", "high_path", "high")]
    trace = run_case(nodes, edges, _case("c1", inputs={"region": "baku", "amount": 100}))
    assert trace.status == "undetermined"
    assert trace.undetermined_reason == "ambiguous_test_cases"


def test_human_override_wins_over_a_matching_test_case():
    nodes = [
        _node("start"),
        _node(
            "h",
            node_type="human",
            test_cases=({"input": {}, "expected_output": {}, "covers_condition": "approve"},),
        ),
        _node("approved"),
        _node("rejected"),
    ]
    edges = [_edge("start", "h"), _edge("h", "approved", "approve"), _edge("h", "rejected", "reject")]
    trace = run_case(nodes, edges, _case("c1", human_overrides={"h": "reject"}))
    assert trace.terminal_node_key == "rejected"


def test_human_node_with_no_override_and_no_matching_test_case_awaits_human():
    nodes = [_node("start"), _node("h", node_type="human"), _node("approved"), _node("rejected")]
    edges = [_edge("start", "h"), _edge("h", "approved", "approve"), _edge("h", "rejected", "reject")]
    trace = run_case(nodes, edges, _case("c1"))
    assert trace.status == "awaiting_human"
    assert trace.terminal_node_key is None


def test_pathological_cycle_hits_step_cap_instead_of_hanging():
    # Deliberately not run through policy_validator first -- an unbounded
    # cycle with a deterministic single unconditional edge at every node.
    nodes = [_node("start"), _node("a"), _node("b")]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a")]
    trace = run_case(nodes, edges, _case("c1"))
    assert trace.status == "undetermined"
    assert trace.undetermined_reason == "step_limit_exceeded"


def test_run_simulation_runs_every_case_in_order():
    nodes = [_node("start"), _node("end")]
    edges = [_edge("start", "end")]
    cases = [_case("a"), _case("b"), _case("c")]
    traces = run_simulation(nodes, edges, cases)
    assert [t.case_id for t in traces] == ["a", "b", "c"]
    assert all(t.status == "completed" for t in traces)


def test_monetary_and_actual_outcome_pass_through_unchanged():
    nodes = [_node("start"), _node("end")]
    edges = [_edge("start", "end")]
    case = _case(
        "c1",
        monetary_amount=Decimal("1234.56"),
        monetary_currency="AZN",
        actual_outcome_label="won",
    )
    trace = run_case(nodes, edges, case)
    assert trace.monetary_amount == Decimal("1234.56")
    assert trace.monetary_currency == "AZN"
    assert trace.actual_outcome_label == "won"


def test_compare_versions_flags_disagreement_and_agreement():
    nodes_a = [_node("start"), _node("approved", reason_codes=("a",))]
    edges_a = [_edge("start", "approved")]

    nodes_b = [_node("start"), _node("rejected", reason_codes=("r",))]
    edges_b = [_edge("start", "rejected")]

    cases = [_case("c1")]
    comparisons = compare_versions(nodes_a, edges_a, nodes_b, edges_b, cases)
    assert len(comparisons) == 1
    comparison = comparisons[0]
    assert comparison.terminal_a == "approved"
    assert comparison.terminal_b == "rejected"
    assert comparison.agrees is False


def test_compare_versions_agrees_on_identical_graphs():
    nodes = [_node("start"), _node("end", reason_codes=("ok",))]
    edges = [_edge("start", "end")]
    comparisons = compare_versions(nodes, edges, nodes, edges, [_case("c1")])
    assert comparisons[0].agrees is True
