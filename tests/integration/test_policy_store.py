"""Integration tests for АЛГОРИТМ policy-graph persistence (Phase 5, task 5.A)."""

from __future__ import annotations

import pytest

from packages.algorithm.policy_model import PolicyEdge, PolicyGraph, PolicyNode
from packages.algorithm.policy_store import (
    ImmutableVersionError,
    InvalidTransitionError,
    add_edges,
    add_nodes,
    create_draft_version,
    create_policy_graph,
    fork_new_draft_version,
    list_edges,
    list_nodes,
    list_transitions_by_version,
    list_versions_by_graph,
    transition_version_status,
)


def _node(policy_version_id: int, node_key: str = "check_qualification", **overrides) -> PolicyNode:
    base = {
        "policy_version_id": policy_version_id,
        "node_key": node_key,
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


async def _new_graph_and_draft(conn, *, name: str = "Bid/No-Bid -- Water Infrastructure") -> tuple[int, int]:
    graph_id = await create_policy_graph(conn, PolicyGraph(name=name, owner="bid_manager"))
    version_id = await create_draft_version(conn, policy_graph_id=graph_id, version_number=1, created_by="bid_manager")
    return graph_id, version_id


async def test_create_graph_and_draft_version(engine):
    async with engine.begin() as conn:
        graph_id, version_id = await _new_graph_and_draft(conn)
        versions = await list_versions_by_graph(conn, policy_graph_id=graph_id)
    assert len(versions) == 1
    assert versions[0]["id"] == version_id
    assert versions[0]["status"] == "draft"
    assert versions[0]["version_number"] == 1


async def test_add_nodes_and_edges_then_list_them_back(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start"), _node(version_id, "end", node_type="gate")])
        await add_edges(conn, [PolicyEdge(policy_version_id=version_id, from_node_key="start", to_node_key="end")])

        nodes = await list_nodes(conn, policy_version_id=version_id)
        edges = await list_edges(conn, policy_version_id=version_id)

    assert {n["node_key"] for n in nodes} == {"start", "end"}
    assert nodes[0]["input_contract"] == {"tender_id": "int"}
    assert nodes[0]["preconditions"] == ["tender_has_boq"]
    assert len(edges) == 1
    assert edges[0]["from_node_key"] == "start"
    assert edges[0]["to_node_key"] == "end"


async def test_transition_status_follows_allowed_graph_and_logs_transition(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await transition_version_status(conn, policy_version_id=version_id, to_status="simulation", changed_by="pm")
        transitions = await list_transitions_by_version(conn, policy_version_id=version_id)

    assert len(transitions) == 1
    assert transitions[0]["from_status"] == "draft"
    assert transitions[0]["to_status"] == "simulation"
    assert transitions[0]["changed_by"] == "pm"


async def test_transition_status_rejects_invalid_transition(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        with pytest.raises(InvalidTransitionError):
            await transition_version_status(conn, policy_version_id=version_id, to_status="approved", changed_by="pm")


async def test_approved_version_content_is_immutable(engine):
    """FR-ALG-11's own exit-gate criterion, proven at 5.A rather than
    deferred entirely to 5.E: once a version reaches an immutable status,
    add_nodes/add_edges refuse to write against it."""
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id)])
        for to_status in ("simulation", "business_review", "risk_review", "approved"):
            await transition_version_status(conn, policy_version_id=version_id, to_status=to_status, changed_by="pm")

        with pytest.raises(ImmutableVersionError):
            await add_nodes(conn, [_node(version_id, "second_node")])
        with pytest.raises(ImmutableVersionError):
            await add_edges(conn, [PolicyEdge(policy_version_id=version_id, from_node_key="a", to_node_key="b")])


async def test_active_version_content_is_also_immutable(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        for to_status in ("simulation", "business_review", "risk_review", "approved", "active"):
            await transition_version_status(conn, policy_version_id=version_id, to_status=to_status, changed_by="pm")

        with pytest.raises(ImmutableVersionError):
            await add_nodes(conn, [_node(version_id)])


async def test_fork_new_draft_version_copies_content_into_a_new_version(engine):
    async with engine.begin() as conn:
        graph_id, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start")])
        await add_edges(conn, [PolicyEdge(policy_version_id=version_id, from_node_key="start", to_node_key="start")])
        for to_status in ("simulation", "business_review", "risk_review", "approved"):
            await transition_version_status(conn, policy_version_id=version_id, to_status=to_status, changed_by="pm")

        new_version_id = await fork_new_draft_version(conn, from_policy_version_id=version_id, created_by="pm")

        versions = await list_versions_by_graph(conn, policy_graph_id=graph_id)
        forked_nodes = await list_nodes(conn, policy_version_id=new_version_id)
        forked_edges = await list_edges(conn, policy_version_id=new_version_id)

    assert new_version_id != version_id
    assert len(versions) == 2
    new_version = next(v for v in versions if v["id"] == new_version_id)
    assert new_version["status"] == "draft"
    assert new_version["version_number"] == 2
    assert [n["node_key"] for n in forked_nodes] == ["start"]
    assert len(forked_edges) == 1

    # The forked draft is content-mutable even though the original it was
    # forked from is approved -- proving fork produces an independent,
    # editable version rather than merely a read-only copy.
    async with engine.begin() as conn:
        await add_nodes(conn, [_node(new_version_id, "second_node")])
        forked_nodes_after = await list_nodes(conn, policy_version_id=new_version_id)
    assert {n["node_key"] for n in forked_nodes_after} == {"start", "second_node"}
