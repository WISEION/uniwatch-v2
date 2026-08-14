"""Integration tests for АЛГОРИТМ policy-graph persistence (Phase 5, tasks 5.A/5.B)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from sqlalchemy import text

from packages.algorithm.policy_model import PolicyEdge, PolicyGraph, PolicyNode
from packages.algorithm.policy_store import (
    GraphInvalidError,
    ImmutableVersionError,
    InvalidTransitionError,
    MakerCheckerViolation,
    activate_version,
    add_edges,
    add_nodes,
    create_draft_version,
    create_policy_graph,
    fork_new_draft_version,
    kill_switch,
    list_edges,
    list_nodes,
    list_transitions_by_version,
    list_versions_by_graph,
    submit_for_approval,
    transition_version_status,
)
from packages.algorithm.research_dossier_model import ResearchDossier
from packages.algorithm.research_dossier_store import link_dossier_to_version, store_research_dossier
from packages.algorithm.simulation_engine import SimulationCase, run_case


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


def _dossier(**overrides) -> ResearchDossier:
    base = {
        "decision_statement": "test-fixture-only, not a real financial decision",
        "owners": ("bid_manager",),
        "approvers": ("finance_lead",),
        "source_register": ({"citation": "test-fixture-only, not a real source"},),
        "assumptions": ("synthetic test assumption",),
        "data_dictionary": {"tender_id": "int"},
        "formula_or_decision_table": {"kind": "test-fixture-only"},
        "coefficients_and_rationale": {"kind": "test-fixture-only"},
        "validation_design": {"kind": "test-fixture-only"},
        "test_dataset_manifest": {"kind": "test-fixture-only"},
        "results_and_limitations": {"kind": "test-fixture-only"},
        "security_privacy_analysis": {"kind": "test-fixture-only"},
        "monitoring_criteria": {"kind": "test-fixture-only"},
        "retirement_criteria": {"kind": "test-fixture-only"},
        "created_by": "bid_manager",
    }
    base.update(overrides)
    return ResearchDossier(**base)


async def _to_risk_review(conn, version_id: int, *, changed_by: str = "pm") -> None:
    for to_status in ("simulation", "business_review", "risk_review"):
        await transition_version_status(conn, policy_version_id=version_id, to_status=to_status, changed_by=changed_by)


async def test_submit_for_approval_rejects_unreachable_node_without_changing_status(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(
            conn,
            [_node(version_id, "start"), _node(version_id, "end", node_type="gate"), _node(version_id, "orphan")],
        )
        await add_edges(conn, [PolicyEdge(policy_version_id=version_id, from_node_key="start", to_node_key="end")])
        await _to_risk_review(conn, version_id)

        with pytest.raises(GraphInvalidError) as exc_info:
            await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        assert any(i.code == "unreachable_node" for i in exc_info.value.issues)

    async with engine.begin() as conn:
        row = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
    assert row == "risk_review"


async def test_submit_for_approval_rejects_financial_node_without_dossier(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start", financial_impact=True)])
        await _to_risk_review(conn, version_id)

        with pytest.raises(GraphInvalidError) as exc_info:
            await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        assert any(i.code == "missing_approved_dossier" for i in exc_info.value.issues)


async def test_submit_for_approval_rejects_financial_node_with_unapproved_dossier(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start", financial_impact=True)])
        dossier_id = await store_research_dossier(conn, _dossier())  # approved_at defaults to None
        await link_dossier_to_version(conn, policy_version_id=version_id, research_dossier_id=dossier_id)
        await _to_risk_review(conn, version_id)

        with pytest.raises(GraphInvalidError) as exc_info:
            await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        assert any(i.code == "missing_approved_dossier" for i in exc_info.value.issues)


async def test_submit_for_approval_accepts_financial_node_with_approved_dossier(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start", financial_impact=True)])
        dossier_id = await store_research_dossier(conn, _dossier(approved_at=datetime.now(UTC).isoformat()))
        await link_dossier_to_version(conn, policy_version_id=version_id, research_dossier_id=dossier_id)
        await _to_risk_review(conn, version_id)

        await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")

        status = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
    assert status == "approved"


async def test_submit_for_approval_rejects_unknown_required_role(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start", required_role="no_such_role")])
        await _to_risk_review(conn, version_id)

        with pytest.raises(GraphInvalidError) as exc_info:
            await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        assert any(i.code == "unknown_role" for i in exc_info.value.issues)


async def test_submit_for_approval_accepts_known_required_role(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await conn.execute(text("INSERT INTO roles (name) VALUES ('bid_manager') ON CONFLICT DO NOTHING"))
        await add_nodes(conn, [_node(version_id, "start", required_role="bid_manager")])
        await _to_risk_review(conn, version_id)

        await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        status = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
    assert status == "approved"


def _rule_branch_edges(version_id: int) -> list[PolicyEdge]:
    return [
        PolicyEdge(policy_version_id=version_id, from_node_key="start", to_node_key="yes_path", condition_label="qualified"),
        PolicyEdge(policy_version_id=version_id, from_node_key="start", to_node_key="no_path", condition_label="not_qualified"),
    ]


async def test_submit_for_approval_rejects_uncovered_rule_branch(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(
            conn,
            [
                _node(version_id, "start", node_type="rule"),
                _node(version_id, "yes_path", node_type="gate"),
                _node(version_id, "no_path", node_type="gate"),
            ],
        )
        await add_edges(conn, _rule_branch_edges(version_id))
        await _to_risk_review(conn, version_id)

        with pytest.raises(GraphInvalidError) as exc_info:
            await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        assert any(i.code == "uncovered_branch" for i in exc_info.value.issues)


async def test_submit_for_approval_accepts_covered_rule_branch(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(
            conn,
            [
                _node(
                    version_id,
                    "start",
                    node_type="rule",
                    test_cases=(
                        {"input": {}, "expected_output": {}, "covers_condition": "qualified"},
                        {"input": {}, "expected_output": {}, "covers_condition": "not_qualified"},
                    ),
                ),
                _node(version_id, "yes_path", node_type="gate"),
                _node(version_id, "no_path", node_type="gate"),
            ],
        )
        await add_edges(conn, _rule_branch_edges(version_id))
        await _to_risk_review(conn, version_id)

        await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        status = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
    assert status == "approved"


async def _new_graph_draft_and_approve(conn, *, financial_impact: bool = False, created_by: str = "designer") -> tuple[int, int]:
    graph_id = await create_policy_graph(conn, PolicyGraph(name="Bid/No-Bid -- Water Infrastructure", owner=created_by))
    version_id = await create_draft_version(conn, policy_graph_id=graph_id, version_number=1, created_by=created_by)
    await add_nodes(conn, [_node(version_id, "start", financial_impact=financial_impact)])
    if financial_impact:
        dossier_id = await store_research_dossier(conn, _dossier(approved_at=datetime.now(UTC).isoformat()))
        await link_dossier_to_version(conn, policy_version_id=version_id, research_dossier_id=dossier_id)
    await _to_risk_review(conn, version_id, changed_by=created_by)
    await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
    return graph_id, version_id


async def test_activate_version_rejects_same_maker_and_checker_for_financial_node(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_draft_and_approve(conn, financial_impact=True, created_by="designer")
        with pytest.raises(MakerCheckerViolation):
            await activate_version(conn, policy_version_id=version_id, changed_by="designer")


async def test_activate_version_accepts_different_maker_and_checker_for_financial_node(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_draft_and_approve(conn, financial_impact=True, created_by="designer")
        await activate_version(conn, policy_version_id=version_id, changed_by="ops_lead")
        status = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
    assert status == "active"


async def test_activate_version_accepts_single_actor_for_non_financial_node(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_draft_and_approve(conn, financial_impact=False, created_by="designer")
        await activate_version(conn, policy_version_id=version_id, changed_by="designer")
        status = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
    assert status == "active"


async def test_activate_version_auto_suspends_previous_active_version_of_same_graph(engine):
    async with engine.begin() as conn:
        graph_id, version_1_id = await _new_graph_draft_and_approve(conn, created_by="designer")
        await activate_version(conn, policy_version_id=version_1_id, changed_by="designer")

        version_2_id = await create_draft_version(conn, policy_graph_id=graph_id, version_number=2, created_by="designer")
        await add_nodes(conn, [_node(version_2_id, "start")])
        await _to_risk_review(conn, version_2_id, changed_by="designer")
        await submit_for_approval(conn, policy_version_id=version_2_id, changed_by="reviewer")
        await activate_version(conn, policy_version_id=version_2_id, changed_by="designer")

        versions = await list_versions_by_graph(conn, policy_graph_id=graph_id)
    by_id = {v["id"]: v for v in versions}
    assert by_id[version_1_id]["status"] == "suspended"
    assert by_id[version_2_id]["status"] == "active"


async def test_activate_version_rollback_reactivates_a_suspended_version(engine):
    async with engine.begin() as conn:
        graph_id, version_1_id = await _new_graph_draft_and_approve(conn, created_by="designer")
        await activate_version(conn, policy_version_id=version_1_id, changed_by="designer")

        version_2_id = await create_draft_version(conn, policy_graph_id=graph_id, version_number=2, created_by="designer")
        await add_nodes(conn, [_node(version_2_id, "start")])
        await _to_risk_review(conn, version_2_id, changed_by="designer")
        await submit_for_approval(conn, policy_version_id=version_2_id, changed_by="reviewer")
        await activate_version(conn, policy_version_id=version_2_id, changed_by="designer")

        # Rollback: reactivate version 1, which is now `suspended`.
        await activate_version(conn, policy_version_id=version_1_id, changed_by="designer")

        versions = await list_versions_by_graph(conn, policy_graph_id=graph_id)
    by_id = {v["id"]: v for v in versions}
    assert by_id[version_1_id]["status"] == "active"
    assert by_id[version_2_id]["status"] == "suspended"


async def test_kill_switch_requires_non_empty_reason(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_draft_and_approve(conn, created_by="designer")
        await activate_version(conn, policy_version_id=version_id, changed_by="designer")
        with pytest.raises(ValueError):
            await kill_switch(conn, policy_version_id=version_id, changed_by="oncall", reason="")


async def test_kill_switch_rejects_non_active_version(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_draft_and_approve(conn, created_by="designer")
        with pytest.raises(ValueError):
            await kill_switch(conn, policy_version_id=version_id, changed_by="oncall", reason="incident-123")


async def test_kill_switch_suspends_active_version_and_logs_reason(engine):
    async with engine.begin() as conn:
        _, version_id = await _new_graph_draft_and_approve(conn, created_by="designer")
        await activate_version(conn, policy_version_id=version_id, changed_by="designer")

        await kill_switch(conn, policy_version_id=version_id, changed_by="oncall", reason="incident-123")

        status = (await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})).scalar_one()
        transitions = await list_transitions_by_version(conn, policy_version_id=version_id)
    assert status == "suspended"
    kill_transition = next(t for t in transitions if t["to_status"] == "suspended")
    assert kill_transition["reason"] == "incident-123"


async def test_rollback_rehearsal_restores_active_versions_behavior_and_keeps_transition_log_visible(engine):
    """Phase 5, task 5.E (FR-ALG-14) -- PLAN-MISSION-5.md Section5's own exit-gate wording is
    "откат к предыдущей approved версии восстанавливает поведение, журнал переходов виден" (rollback to a
    previously-approved version restores behavior, transition log is visible). 5.B's own
    test_activate_version_rollback_reactivates_a_suspended_version only asserted the status flip; this
    test additionally proves BEHAVIOR is restored (via 5.C's simulation engine, run against whichever
    version list_versions_by_graph currently reports as active -- not a hardcoded version id) and that the
    full transition history remains visible across the whole rehearsal, not just the rollback step."""
    async with engine.begin() as conn:
        graph_id, version_1_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_1_id, "start", node_type="gate", reason_codes=("v1_result",))])
        await _to_risk_review(conn, version_1_id)
        await submit_for_approval(conn, policy_version_id=version_1_id, changed_by="reviewer")
        await activate_version(conn, policy_version_id=version_1_id, changed_by="designer")

        version_2_id = await create_draft_version(conn, policy_graph_id=graph_id, version_number=2, created_by="designer")
        await add_nodes(conn, [_node(version_2_id, "start", node_type="gate", reason_codes=("v2_result",))])
        await _to_risk_review(conn, version_2_id)
        await submit_for_approval(conn, policy_version_id=version_2_id, changed_by="reviewer")
        await activate_version(conn, policy_version_id=version_2_id, changed_by="designer")

        case = SimulationCase(case_id="c1", inputs={})
        nodes_v2 = await list_nodes(conn, policy_version_id=version_2_id)
        edges_v2 = await list_edges(conn, policy_version_id=version_2_id)
        trace_before_rollback = run_case(nodes_v2, edges_v2, case)
        assert trace_before_rollback.reason_codes == ("v2_result",)  # confirms the two versions really differ

        # Rollback: reactivate version 1 (currently `suspended`, per 5.B's activate_version).
        await activate_version(conn, policy_version_id=version_1_id, changed_by="designer")

        versions = await list_versions_by_graph(conn, policy_graph_id=graph_id)
        active_version = next(v for v in versions if v["status"] == "active")
        assert active_version["id"] == version_1_id  # not hardcoded -- this is what "current" means post-rollback

        nodes_active = await list_nodes(conn, policy_version_id=active_version["id"])
        edges_active = await list_edges(conn, policy_version_id=active_version["id"])
        trace_after_rollback = run_case(nodes_active, edges_active, case)

        transitions_v1 = await list_transitions_by_version(conn, policy_version_id=version_1_id)

    assert trace_after_rollback.reason_codes == ("v1_result",)  # behavior restored, not v2's
    assert [t["to_status"] for t in transitions_v1] == [
        "simulation",
        "business_review",
        "risk_review",
        "approved",
        "active",
        "suspended",
        "active",
    ]  # the full lifecycle, including the rollback step itself, stays visible in one log


async def test_kill_switch_rehearsal_preserves_prior_journal_and_allows_reactivation(engine):
    """Phase 5, task 5.E (FR-ALG-13) -- proves the kill switch is a real, auditable incident-response
    action, not a destructive one: every transition recorded before the kill switch survives unchanged
    (by id and content), and the version can be reactivated afterward rather than being a dead end."""
    async with engine.begin() as conn:
        _, version_id = await _new_graph_and_draft(conn)
        await add_nodes(conn, [_node(version_id, "start")])
        await _to_risk_review(conn, version_id)
        await submit_for_approval(conn, policy_version_id=version_id, changed_by="reviewer")
        await activate_version(conn, policy_version_id=version_id, changed_by="designer")

        transitions_before = await list_transitions_by_version(conn, policy_version_id=version_id)
        assert len(transitions_before) == 5  # draft->simulation->business_review->risk_review->approved->active

        await kill_switch(conn, policy_version_id=version_id, changed_by="oncall", reason="incident-123")
        transitions_after_kill = await list_transitions_by_version(conn, policy_version_id=version_id)

        before_by_id = {t["id"]: t for t in transitions_before}
        after_by_id = {t["id"]: t for t in transitions_after_kill}
        for transition_id, original_row in before_by_id.items():
            assert after_by_id[transition_id] == original_row  # nothing about prior history changed
        assert len(transitions_after_kill) == len(transitions_before) + 1

        status_after_kill = (
            await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})
        ).scalar_one()
        assert status_after_kill == "suspended"

        # Reversible: kill switch is not a dead end for the version.
        await activate_version(conn, policy_version_id=version_id, changed_by="designer")
        status_after_reactivation = (
            await conn.execute(text("SELECT status FROM policy_versions WHERE id = :id"), {"id": version_id})
        ).scalar_one()
        transitions_final = await list_transitions_by_version(conn, policy_version_id=version_id)

    assert status_after_reactivation == "active"
    assert len(transitions_final) == len(transitions_before) + 2
    assert transitions_final[-1]["to_status"] == "active"
