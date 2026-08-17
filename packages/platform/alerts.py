"""Platform-scoped alert checks (Phase 6, task 6.C, NFR-OPS-02: freshness/
job-failure/invariant-violation/exception-queue-growth alerts). Each check
takes the same live AsyncConnection every packages/*_store.py module uses
and returns an AlertResult -- name/firing/detail, never a bare boolean
(hard ban #3: a firing alert is always actionable, not just "true").

Two of NFR-OPS-02's four categories cannot honestly carry a numeric
threshold yet -- D-SLO/TBD-01/TBD-02 remain open (AGENTS.md hard ban #2:
never invent a number) -- so `exception_queue_has_open_items` fires on "any
open row at all" (a genuinely boolean, threshold-free condition), not a
growth-rate window. True growth-rate detection would need a persisted
sample-history table this repo does not have; recorded as an honest gap in
docs/decisions/OPEN-QUESTIONS.md's 2026-08-17 entry, not approximated here.

Source-freshness alerting needs packages/tender-owned data (raw_snapshots)
and lives in packages/tender/freshness_alerts.py instead -- packages/platform
never depends on a domain package (AGENTS.md §3). scripts/check_alerts.py is
the one place both lists are combined."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncConnection

from .exception_queue import list_open
from .invariant_checks import ALL_CHECKS
from .jobs import JobStore


@dataclass(frozen=True)
class AlertResult:
    name: str
    firing: bool
    detail: str


AlertCheck = Callable[[AsyncConnection], Awaitable[AlertResult]]


async def dead_lettered_jobs_present(conn: AsyncConnection) -> AlertResult:
    dead = await JobStore().list_dead_lettered(conn)
    if dead:
        ids = ", ".join(str(job.id) for job in dead)
        return AlertResult(name="dead_lettered_jobs_present", firing=True, detail=f"{len(dead)} dead-lettered job(s): {ids}")
    return AlertResult(name="dead_lettered_jobs_present", firing=False, detail="no dead-lettered jobs")


async def exception_queue_has_open_items(conn: AsyncConnection) -> AlertResult:
    open_items = await list_open(conn)
    if open_items:
        return AlertResult(
            name="exception_queue_has_open_items", firing=True, detail=f"{len(open_items)} open exception_queue row(s)"
        )
    return AlertResult(name="exception_queue_has_open_items", firing=False, detail="exception queue is empty")


async def invariant_violation_detected(conn: AsyncConnection) -> AlertResult:
    failing_names = []
    for check in ALL_CHECKS:
        result = await check(conn)
        if not result.passed:
            failing_names.append(result.name)
    if failing_names:
        return AlertResult(
            name="invariant_violation_detected", firing=True, detail=f"failing invariant(s): {', '.join(failing_names)}"
        )
    return AlertResult(name="invariant_violation_detected", firing=False, detail="all DB invariants pass")


ALL_ALERTS: tuple[AlertCheck, ...] = (
    dead_lettered_jobs_present,
    exception_queue_has_open_items,
    invariant_violation_detected,
)
