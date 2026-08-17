"""Signal aggregation (Phase 6, task 6.C, master plan §23.1). Confirms every
signal category is present in the payload, including the honest
not_applicable entries for categories this repo has no real data source
for."""

from __future__ import annotations

from pathlib import Path

from scripts.collect_signals import collect_signals


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
    ):
        assert key in payload, f"missing signal category: {key}"

    assert payload["notification_delivery"]["status"] == "not_applicable"
    assert payload["model_drift_confidence_abstention"]["status"] == "not_applicable"
    assert payload["reconciliation_mismatches"]["status"] == "not_applicable"
    assert payload["backup"]["latest_backup_at"] is None  # tmp_path has no backup files
