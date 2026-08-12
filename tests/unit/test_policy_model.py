"""Unit tests for the АЛГОРИТМ policy-graph domain model (Phase 5, task 5.A)."""

from __future__ import annotations

import pytest

from packages.algorithm.policy_model import PolicyEdge, PolicyGraph, PolicyNode, PolicyVersion


def _node(**overrides) -> PolicyNode:
    base = {
        "policy_version_id": 1,
        "node_key": "check_qualification",
        "node_type": "human",
        "title": "Check qualification",
        "purpose": "Confirm bidder meets qualification requirements",
        "owner": "bid_manager",
        "execution_mode": "manual",
        "input_contract": {"tender_id": "int"},
        "output_contract": {"qualified": "bool"},
        "preconditions": ("tender_has_boq",),
        "evidence_requirements": ("license_document",),
        "reason_codes": ("missing_license",),
        "test_cases": ({"input": {"tender_id": 1}, "expected_output": {"qualified": True}},),
        "monitoring_metrics": ("time_to_decision",),
    }
    base.update(overrides)
    return PolicyNode(**base)


def test_policy_graph_requires_no_special_validation():
    graph = PolicyGraph(name="Bid/No-Bid -- Water Infrastructure", owner="bid_manager")
    assert graph.description is None


def test_policy_version_rejects_unknown_status():
    with pytest.raises(ValueError, match="unknown lifecycle status"):
        PolicyVersion(policy_graph_id=1, version_number=1, status="not_a_real_status", created_by="pm")


def test_policy_version_rejects_non_positive_version_number():
    with pytest.raises(ValueError, match="version_number"):
        PolicyVersion(policy_graph_id=1, version_number=0, status="draft", created_by="pm")


def test_policy_node_accepts_human_rule_gate_data_quality():
    for node_type in ("human", "rule", "gate", "data_quality"):
        node = _node(node_type=node_type)
        assert node.node_type == node_type


def test_policy_node_rejects_ml_node_type_fr_alg_08():
    with pytest.raises(ValueError, match="not activatable until Phase 8"):
        _node(node_type="ml")


def test_policy_node_rejects_hybrid_node_type_fr_alg_08():
    with pytest.raises(ValueError, match="not activatable until Phase 8"):
        _node(node_type="hybrid")


def test_policy_node_rejects_blank_node_key():
    with pytest.raises(ValueError, match="node_key"):
        _node(node_key="  ")


def test_policy_node_rejects_unknown_node_type_outright():
    with pytest.raises(ValueError, match="unknown node_type"):
        _node(node_type="something_invented")


def test_policy_edge_rejects_blank_endpoints():
    with pytest.raises(ValueError, match="from_node_key/to_node_key"):
        PolicyEdge(policy_version_id=1, from_node_key="", to_node_key="next")
