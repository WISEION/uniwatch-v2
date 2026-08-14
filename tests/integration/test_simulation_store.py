"""Integration tests for АЛГОРИТМ simulation/backtest run persistence
(Phase 5, task 5.C)."""

from __future__ import annotations

from decimal import Decimal

from packages.algorithm.policy_model import PolicyGraph
from packages.algorithm.policy_store import create_draft_version, create_policy_graph
from packages.algorithm.simulation_engine import CaseTrace, VersionComparison
from packages.algorithm.simulation_store import (
    get_simulation_run,
    list_case_traces,
    list_simulation_runs_by_version,
    record_comparison_run,
    record_simulation_run,
)


async def _new_version(conn, *, name: str = "Bid/No-Bid -- test") -> int:
    graph_id = await create_policy_graph(conn, PolicyGraph(name=name, owner="bid_manager"))
    return await create_draft_version(conn, policy_graph_id=graph_id, version_number=1, created_by="bid_manager")


def _trace(case_id: str, **overrides) -> CaseTrace:
    base = {
        "case_id": case_id,
        "status": "completed",
        "path": ("start", "end"),
        "terminal_node_key": "end",
        "reason_codes": ("ok",),
        "undetermined_reason": None,
        "final_state": {},
        "monetary_amount": None,
        "monetary_currency": None,
        "actual_outcome_label": None,
    }
    base.update(overrides)
    return CaseTrace(**base)


async def test_record_run_computes_status_counts_and_distributions(engine):
    async with engine.begin() as conn:
        version_id = await _new_version(conn)
        traces = (
            _trace("c1", status="completed", terminal_node_key="approved", reason_codes=("ok",)),
            _trace("c2", status="completed", terminal_node_key="approved", reason_codes=("ok",)),
            _trace("c3", status="awaiting_human", terminal_node_key=None, reason_codes=()),
            _trace(
                "c4",
                status="undetermined",
                terminal_node_key=None,
                reason_codes=(),
                undetermined_reason="no_matching_test_case",
            ),
        )
        run_id = await record_simulation_run(
            conn,
            policy_version_id=version_id,
            case_set_label="smoke-test-batch",
            case_source="synthetic_vendor",
            traces=traces,
            run_by="qa_engineer",
        )
        run = await get_simulation_run(conn, run_id=run_id)

    assert run is not None
    assert run["case_count"] == 4
    assert run["completed_count"] == 2
    assert run["awaiting_human_count"] == 1
    assert run["undetermined_count"] == 1
    assert run["terminal_distribution"] == {"approved": 2}
    assert run["reason_code_distribution"] == {"ok": 2}


async def test_monetary_range_groups_by_currency_and_excludes_uncurrencied(engine):
    async with engine.begin() as conn:
        version_id = await _new_version(conn)
        traces = (
            _trace("c1", terminal_node_key="approved", monetary_amount=Decimal("100"), monetary_currency="AZN"),
            _trace("c2", terminal_node_key="approved", monetary_amount=Decimal("300"), monetary_currency="AZN"),
            _trace("c3", terminal_node_key="approved", monetary_amount=Decimal("50"), monetary_currency="USD"),
            _trace("c4", terminal_node_key="approved", monetary_amount=Decimal("999"), monetary_currency=None),
        )
        run_id = await record_simulation_run(
            conn,
            policy_version_id=version_id,
            case_set_label="money-batch",
            case_source="frozen_real_tender",
            traces=traces,
            run_by="qa_engineer",
        )
        run = await get_simulation_run(conn, run_id=run_id)

    assert run is not None
    assert run["monetary_amount_uncurrencied_count"] == 1
    monetary_range = run["monetary_range"]
    azn_key = "approved::AZN"
    usd_key = "approved::USD"
    assert monetary_range[azn_key]["min"] == "100"
    assert monetary_range[azn_key]["max"] == "300"
    assert monetary_range[azn_key]["count"] == 2
    assert monetary_range[usd_key]["count"] == 1
    # the uncurrencied 999 must not be folded into either currency's range
    assert "999" not in str(monetary_range)


async def test_list_case_traces_round_trips_actual_outcome_label_including_absence(engine):
    async with engine.begin() as conn:
        version_id = await _new_version(conn)
        traces = (
            _trace("c1", actual_outcome_label="won"),
            _trace("c2", actual_outcome_label=None),
        )
        run_id = await record_simulation_run(
            conn,
            policy_version_id=version_id,
            case_set_label="review-queue-batch",
            case_source="historical_outcome",
            traces=traces,
            run_by="qa_engineer",
        )
        case_traces = await list_case_traces(conn, run_id=run_id)

    by_case = {t["case_id"]: t for t in case_traces}
    assert by_case["c1"]["actual_outcome_label"] == "won"
    assert by_case["c2"]["actual_outcome_label"] is None


async def test_record_and_read_back_comparison_run(engine):
    async with engine.begin() as conn:
        version_a = await _new_version(conn, name="graph-a")
        version_b = await _new_version(conn, name="graph-b")
        comparisons = (
            VersionComparison("c1", "approved", "approved", ("ok",), ("ok",), agrees=True),
            VersionComparison("c2", "approved", "rejected", ("ok",), ("no",), agrees=False),
        )
        run_id = await record_comparison_run(
            conn,
            policy_version_id=version_a,
            compared_against_version_id=version_b,
            case_set_label="candidate-vs-active",
            comparisons=comparisons,
            run_by="policy_designer",
        )
        run = await get_simulation_run(conn, run_id=run_id)

    assert run is not None
    assert run["case_source"] == "mixed"
    assert run["compared_against_version_id"] == version_b
    assert run["terminal_distribution"] == {"agree": 1, "disagree": 1}
    assert run["case_traces"][0]["kind"] == "comparison"


async def test_list_simulation_runs_by_version_returns_multiple_runs_in_order(engine):
    async with engine.begin() as conn:
        version_id = await _new_version(conn)
        first_id = await record_simulation_run(
            conn,
            policy_version_id=version_id,
            case_set_label="batch-1",
            case_source="synthetic_vendor",
            traces=(_trace("c1"),),
            run_by="qa_engineer",
        )
        second_id = await record_simulation_run(
            conn,
            policy_version_id=version_id,
            case_set_label="batch-2",
            case_source="synthetic_vendor",
            traces=(_trace("c1"), _trace("c2")),
            run_by="qa_engineer",
        )
        runs = await list_simulation_runs_by_version(conn, policy_version_id=version_id)

    assert [r["id"] for r in runs] == [first_id, second_id]
    assert [r["case_set_label"] for r in runs] == ["batch-1", "batch-2"]
