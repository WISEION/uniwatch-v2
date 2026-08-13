"""Integration tests for ALG-RESEARCH dossier persistence (Phase 5, task 5.A,
docs/adr/0007-algorithm-research-dossier-schema.md)."""

from __future__ import annotations

from packages.algorithm.policy_model import PolicyGraph
from packages.algorithm.policy_store import create_draft_version, create_policy_graph, list_versions_by_graph
from packages.algorithm.research_dossier_model import ResearchDossier
from packages.algorithm.research_dossier_store import get_research_dossier, link_dossier_to_version, store_research_dossier


def _dossier(**overrides) -> ResearchDossier:
    base = {
        "decision_statement": "Test-only candidate algorithm B skeleton, no coefficients approved",
        "owners": ("algo_owner",),
        "approvers": ("risk_committee",),
        "source_register": ({"name": "test source", "citation": "internal test fixture"},),
        "assumptions": ("bidder pool is representative",),
        "data_dictionary": {"bid_amount": "numeric"},
        "formula_or_decision_table": {"note": "skeleton only, TBD-04 unresolved"},
        "coefficients_and_rationale": {"note": "no coefficients approved -- TBD-04"},
        "validation_design": {"method": "backtest against >=30 tenders, not yet run"},
        "test_dataset_manifest": {"tenders": []},
        "results_and_limitations": {"note": "no results yet"},
        "security_privacy_analysis": {"note": "no PII involved"},
        "monitoring_criteria": {"note": "not yet defined"},
        "retirement_criteria": {"note": "not yet defined"},
        "created_by": "algo_owner",
    }
    base.update(overrides)
    return ResearchDossier(**base)


async def test_store_and_get_research_dossier_roundtrips_all_fields(engine):
    async with engine.begin() as conn:
        dossier_id = await store_research_dossier(conn, _dossier())
        loaded = await get_research_dossier(conn, dossier_id=dossier_id)

    assert loaded is not None
    assert loaded["decision_statement"] == "Test-only candidate algorithm B skeleton, no coefficients approved"
    assert loaded["owners"] == ["algo_owner"]
    assert loaded["source_register"] == [{"name": "test source", "citation": "internal test fixture"}]
    assert loaded["fairness_analysis"] is None


async def test_fairness_analysis_roundtrips_when_supplied(engine):
    async with engine.begin() as conn:
        dossier_id = await store_research_dossier(conn, _dossier(fairness_analysis={"note": "checked"}))
        loaded = await get_research_dossier(conn, dossier_id=dossier_id)

    assert loaded["fairness_analysis"] == {"note": "checked"}


async def test_link_dossier_to_version(engine):
    async with engine.begin() as conn:
        graph_id = await create_policy_graph(conn, PolicyGraph(name="Test policy", owner="bid_manager"))
        version_id = await create_draft_version(conn, policy_graph_id=graph_id, version_number=1, created_by="bid_manager")
        dossier_id = await store_research_dossier(conn, _dossier())

        await link_dossier_to_version(conn, policy_version_id=version_id, research_dossier_id=dossier_id)

        versions = await list_versions_by_graph(conn, policy_graph_id=graph_id)

    assert versions[0]["research_dossier_id"] == dossier_id


async def test_get_research_dossier_returns_none_for_unknown_id(engine):
    async with engine.begin() as conn:
        loaded = await get_research_dossier(conn, dossier_id=999999)
    assert loaded is None
