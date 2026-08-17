"""Aggregates every observability signal this repo can honestly compute
today (Phase 6, task 6.C, master plan §23.1) into one JSON payload -- the
read side dashboards/alerts consume. Three of §23.1's named signal
categories have no real data source anywhere in this codebase and are
reported as such (`"status": "not_applicable"`, hard ban #3: no silent
fallback) rather than fabricated or silently dropped: notification_delivery
(no notifications table is created by any real migration --
packages/platform/invariant_checks.py's own no_orphaned_notifications found
the same gap), model_drift_confidence_abstention (no ML/model code exists
anywhere in this repo -- only rule/human policy-graph nodes; ml/hybrid node
types are schema-valid but rejected at construction), and
reconciliation_mismatches (packages/tender/shadow_comparison.py's classify
functions are pure and unpersisted -- no run-history table exists, per task
6.A's own record)."""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from packages.algorithm.policy_store import list_all_active_versions
from packages.decision.decision_store import list_decision_cycle_seconds
from packages.platform.backup_signals import latest_backup_at
from packages.platform.db import connection_scope, get_engine
from packages.platform.db_signals import connection_and_storage_signals
from packages.platform.exception_queue import last_seen_by_source, list_open
from packages.platform.jobs import JobStore
from packages.platform.restore_drill import latest_passing_drill
from packages.platform.settings import get_settings
from packages.tender.boq_completeness import count_by_status as boq_count_by_status
from packages.tender.raw_snapshot import last_fetched_at_by_source

_NOT_APPLICABLE: dict[str, str] = {
    "notification_delivery": (
        "no notifications table is created by any real migration "
        "(see packages/platform/invariant_checks.py::no_orphaned_notifications)"
    ),
    "model_drift_confidence_abstention": (
        "no ML/model code exists in this repo; ml/hybrid policy nodes are schema-valid but rejected at construction"
    ),
    "reconciliation_mismatches": (
        "packages/tender/shadow_comparison.py classifications are pure and unpersisted; no run-history table exists"
    ),
}


def _jsonable(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.isoformat()
    if isinstance(value, dict):
        return {key: _jsonable(v) for key, v in value.items()}
    if isinstance(value, list):
        return [_jsonable(v) for v in value]
    return value


async def collect_signals(database_url: str, backup_dir: Path) -> dict[str, Any]:
    engine = get_engine(database_url)
    job_store = JobStore()
    try:
        async with connection_scope(engine) as conn:
            payload: dict[str, Any] = {
                "job_queue": {
                    "by_status": await job_store.count_by_status(conn),
                    "dead_lettered_count": len(await job_store.list_dead_lettered(conn)),
                },
                "exception_queue": {
                    "open_count": len(await list_open(conn)),
                    "last_seen_by_source": await last_seen_by_source(conn),
                },
                "source_freshness": {
                    "last_fetched_at_by_source": await last_fetched_at_by_source(conn),
                },
                "boq_completeness": {
                    "by_status": await boq_count_by_status(conn),
                },
                "decision_cycle": {
                    "cycles": await list_decision_cycle_seconds(conn),
                },
                "policy_version_usage": {
                    "active_versions": await list_all_active_versions(conn),
                },
                "database": await connection_and_storage_signals(conn),
                "restore_drill": {
                    "latest_passing": await latest_passing_drill(conn),
                },
            }
    finally:
        await engine.dispose()

    payload["backup"] = {"latest_backup_at": latest_backup_at(backup_dir)}
    for key, reason in _NOT_APPLICABLE.items():
        payload[key] = {"status": "not_applicable", "reason": reason}

    return _jsonable(payload)


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Collect UNIWatch v2 observability signals as JSON.")
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args(argv)

    settings = get_settings()
    payload = await collect_signals(settings.database_url, args.backup_dir)
    print(json.dumps(payload, indent=2, sort_keys=True))
    return 0


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    sys.exit(main())
