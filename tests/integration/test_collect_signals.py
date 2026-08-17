"""Signal aggregation (Phase 6, task 6.C, master plan §23.1). Confirms every
signal category is present in the payload, including the honest
not_applicable entries for categories this repo has no real data source
for."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from scripts.collect_signals import _jsonable, collect_signals


async def test_collect_signals_returns_every_named_category(engine, _database_url, tmp_path: Path):
    payload = await collect_signals(_database_url, tmp_path)

    for key in (
        "job_queue",
        "exception_queue",
        "source_freshness",
        "boq_completeness",
        "decision_cycle",
        "policy_version_usage",
        "database",
        "restore_drill",
        "backup",
        "notification_delivery",
        "model_drift_confidence_abstention",
        "reconciliation_mismatches",
        "request_latency_by_route",
        "decision_override_agreement",
    ):
        assert key in payload, f"missing signal category: {key}"

    assert payload["notification_delivery"]["status"] == "not_applicable"
    assert payload["model_drift_confidence_abstention"]["status"] == "not_applicable"
    assert payload["reconciliation_mismatches"]["status"] == "not_applicable"
    assert payload["request_latency_by_route"]["status"] == "not_applicable"
    assert payload["decision_override_agreement"]["status"] == "not_applicable"
    assert payload["backup"]["latest_backup_at"] is None  # tmp_path has no backup files


async def test_collect_signals_json_dumps_a_real_decision_cycle_with_a_decimal_value(engine, _database_url, tmp_path: Path):
    # Regression test for the Decimal-not-JSON-serializable bug (C1, final
    # whole-branch review): EXTRACT(EPOCH FROM (...)) comes back from
    # asyncpg as decimal.Decimal, which json.dumps() cannot serialize
    # unchanged. Seed one real tender + bid_readiness_candidate + decision
    # so decision_cycle.cycles is non-empty and actually exercises this path
    # -- the category-presence test above never does, since it runs against
    # an empty schema.
    from packages.decision.bid_readiness import BidReadinessCandidate
    from packages.decision.boq_summary import BoqMatchSummary
    from packages.decision.decision_model import Decision
    from packages.decision.decision_store import store_bid_readiness_candidate, store_decision
    from packages.tender.normalized import create_normalized_version, get_or_create_tender
    from packages.tender.raw_snapshot import save_raw_snapshot

    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-collect-signals-decision-cycle",
            raw_body=json.dumps({"eventId": 1}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-collect-signals",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-collect-signals-decision-cycle")
        await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        summary = BoqMatchSummary(
            green_amount=Decimal("1000"),
            yellow_amount=Decimal("0"),
            red_amount=Decimal("0"),
            unpriced_line_count=0,
            non_matchable_line_count=0,
            non_matchable_amount=Decimal("0"),
            total_priced_amount=Decimal("1000"),
            green_pct=100.0,
            yellow_pct=0.0,
            red_pct=0.0,
        )
        candidate = BidReadinessCandidate(
            tender_id=tender_id,
            summary=summary,
            is_lottery=False,
            critical_lines=(),
            computed_at="2026-08-08T00:00:00+00:00",
        )
        candidate_id = await store_bid_readiness_candidate(conn, candidate)
        decision = Decision(
            tender_id=tender_id,
            decision_type="bid",
            conditions=(),
            deadline=None,
            justification="test",
            actor="pm-1",
            decided_at="2026-08-09T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=candidate_id,
        )
        await store_decision(conn, decision)

    payload = await collect_signals(_database_url, tmp_path)

    cycles = payload["decision_cycle"]["cycles"]
    matching = [c for c in cycles if c["tender_id"] == tender_id]
    assert len(matching) == 1
    assert matching[0]["cycle_seconds"] == 86400.0

    # This is the assertion that would have caught the original bug: a
    # Decimal surviving unchanged into the payload raises TypeError here.
    json.dumps(payload)


def test_jsonable_raises_loudly_for_an_unrecognized_type():
    class _Unrecognized:
        pass

    try:
        _jsonable(_Unrecognized())
    except TypeError:
        pass
    else:
        raise AssertionError("expected _jsonable to raise TypeError for an unrecognized type")
