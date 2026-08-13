"""Unit tests for the АЛГОРИТМ policy-graph structural + branch-coverage
validator (Phase 5, task 5.B)."""

from __future__ import annotations

from packages.algorithm.policy_validator import (
    check_branch_coverage,
    validate_graph,
    validate_graph_structure,
)


def _node(node_key: str, node_type: str = "human", **overrides) -> dict:
    base = {
        "node_key": node_key,
        "node_type": node_type,
        "input_contract": {},
        "output_contract": {},
        "fallback_node_key": None,
        "retry_policy": None,
        "test_cases": (),
    }
    base.update(overrides)
    return base


def _edge(from_node_key: str, to_node_key: str, condition_label: str | None = None) -> dict:
    return {"from_node_key": from_node_key, "to_node_key": to_node_key, "condition_label": condition_label}


def test_empty_graph_is_flagged():
    issues = validate_graph_structure([], [])
    assert {i.code for i in issues} == {"empty_graph"}


def test_minimal_linear_graph_is_clean():
    nodes = [_node("start"), _node("end", node_type="gate")]
    edges = [_edge("start", "end")]
    assert validate_graph_structure(nodes, edges) == ()


def test_dangling_edge_reference_is_flagged():
    nodes = [_node("start")]
    edges = [_edge("start", "ghost")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "dangling_reference" and i.node_key == "ghost" for i in issues)


def test_dangling_fallback_reference_is_flagged():
    nodes = [_node("start", fallback_node_key="ghost")]
    issues = validate_graph_structure(nodes, [])
    assert any(i.code == "dangling_reference" and i.node_key == "start" for i in issues)


def test_no_start_node_when_every_node_has_an_incoming_edge():
    nodes = [_node("a"), _node("b")]
    edges = [_edge("a", "b"), _edge("b", "a")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "no_start_node" for i in issues)


def test_unreachable_node_is_flagged():
    nodes = [_node("start"), _node("end", node_type="gate"), _node("orphan")]
    edges = [_edge("start", "end")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "unreachable_node" and i.node_key == "orphan" for i in issues)


def test_no_reachable_terminal_when_every_reachable_node_has_an_outgoing_edge():
    # start has a real entry point (zero incoming edges), but every node
    # reachable from it is itself part of a cycle -- no sink is ever reached.
    nodes = [_node("start", node_type="human"), _node("a", node_type="human"), _node("b", node_type="human")]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a")]
    issues = validate_graph_structure(nodes, edges)
    codes = {i.code for i in issues}
    assert "no_reachable_terminal" in codes
    assert "no_start_node" not in codes


def test_unbounded_cycle_without_human_or_bounded_retry_is_flagged():
    nodes = [_node("a", node_type="rule"), _node("b", node_type="rule"), _node("start")]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "unbounded_cycle_no_exit" for i in issues)


def test_cycle_with_human_node_is_not_flagged():
    nodes = [_node("a", node_type="human"), _node("b", node_type="rule"), _node("start"), _node("end", node_type="gate")]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a"), _edge("b", "end")]
    issues = validate_graph_structure(nodes, edges)
    assert not any(i.code == "unbounded_cycle_no_exit" for i in issues)


def test_cycle_with_bounded_retry_and_external_fallback_is_not_flagged():
    nodes = [
        _node("start"),
        _node(
            "a",
            node_type="rule",
            retry_policy={"max_attempts": 3},
            fallback_node_key="escape",
        ),
        _node("b", node_type="rule"),
        _node("escape", node_type="gate"),
    ]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a")]
    issues = validate_graph_structure(nodes, edges)
    assert not any(i.code == "unbounded_cycle_no_exit" for i in issues)


def test_cycle_with_bounded_retry_but_fallback_inside_cycle_is_flagged():
    nodes = [
        _node("start"),
        _node("a", node_type="rule", retry_policy={"max_attempts": 3}, fallback_node_key="b"),
        _node("b", node_type="rule"),
    ]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "unbounded_cycle_no_exit" for i in issues)


def test_self_loop_without_exit_is_flagged():
    nodes = [_node("start"), _node("a", node_type="rule")]
    edges = [_edge("start", "a"), _edge("a", "a")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "unbounded_cycle_no_exit" for i in issues)


def test_io_type_mismatch_on_shared_field_is_flagged():
    nodes = [
        _node("start", output_contract={"tender_id": "int"}),
        _node("end", node_type="gate", input_contract={"tender_id": "str"}),
    ]
    edges = [_edge("start", "end")]
    issues = validate_graph_structure(nodes, edges)
    assert any(i.code == "io_type_mismatch" for i in issues)


def test_io_type_match_on_shared_field_is_not_flagged():
    nodes = [
        _node("start", output_contract={"tender_id": "int"}),
        _node("end", node_type="gate", input_contract={"tender_id": "int", "extra": "bool"}),
    ]
    edges = [_edge("start", "end")]
    issues = validate_graph_structure(nodes, edges)
    assert not any(i.code == "io_type_mismatch" for i in issues)


def test_rule_node_with_branches_and_no_test_cases_is_flagged():
    nodes = [_node("start"), _node("r", node_type="rule"), _node("a", node_type="gate"), _node("b", node_type="gate")]
    edges = [_edge("start", "r"), _edge("r", "a", "qualified"), _edge("r", "b", "not_qualified")]
    issues = check_branch_coverage(nodes, edges)
    assert any(i.code == "no_test_cases" and i.node_key == "r" for i in issues)


def test_rule_node_with_uncovered_branch_is_flagged():
    nodes = [
        _node("start"),
        _node(
            "r",
            node_type="rule",
            test_cases=({"input": {}, "expected_output": {}, "covers_condition": "qualified"},),
        ),
        _node("a", node_type="gate"),
        _node("b", node_type="gate"),
    ]
    edges = [_edge("start", "r"), _edge("r", "a", "qualified"), _edge("r", "b", "not_qualified")]
    issues = check_branch_coverage(nodes, edges)
    assert any(i.code == "uncovered_branch" and i.node_key == "r" for i in issues)


def test_rule_node_with_every_branch_covered_is_clean():
    nodes = [
        _node("start"),
        _node(
            "r",
            node_type="rule",
            test_cases=(
                {"input": {}, "expected_output": {}, "covers_condition": "qualified"},
                {"input": {}, "expected_output": {}, "covers_condition": "not_qualified"},
            ),
        ),
        _node("a", node_type="gate"),
        _node("b", node_type="gate"),
    ]
    edges = [_edge("start", "r"), _edge("r", "a", "qualified"), _edge("r", "b", "not_qualified")]
    assert check_branch_coverage(nodes, edges) == ()


def test_rule_node_with_single_unconditional_branch_needs_only_one_test_case():
    nodes = [
        _node("start"),
        _node("r", node_type="rule", test_cases=({"input": {}, "expected_output": {}},)),
        _node("end", node_type="gate"),
    ]
    edges = [_edge("start", "r"), _edge("r", "end")]
    assert check_branch_coverage(nodes, edges) == ()


def test_non_rule_node_branches_are_not_subject_to_coverage():
    nodes = [_node("start"), _node("g", node_type="gate"), _node("a", node_type="gate"), _node("b", node_type="gate")]
    edges = [_edge("start", "g"), _edge("g", "a", "yes"), _edge("g", "b", "no")]
    assert check_branch_coverage(nodes, edges) == ()


def test_node_reachable_only_via_fallback_is_not_flagged_as_an_island():
    nodes = [
        _node("start"),
        _node("a", node_type="rule", retry_policy={"max_attempts": 3}, fallback_node_key="escape"),
        _node("b", node_type="rule"),
        _node("escape", node_type="gate"),
    ]
    edges = [_edge("start", "a"), _edge("a", "b"), _edge("b", "a")]
    issues = validate_graph_structure(nodes, edges)
    assert not any(i.code == "unreachable_node" for i in issues)
    assert not any(i.code == "no_reachable_terminal" for i in issues)


def test_validate_graph_combines_structure_and_coverage():
    nodes = [_node("start"), _node("r", node_type="rule")]
    edges = [_edge("start", "r"), _edge("r", "ghost")]
    issues = validate_graph(nodes, edges)
    codes = {i.code for i in issues}
    assert "dangling_reference" in codes
