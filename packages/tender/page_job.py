"""Shared resumable-page-job mechanism (INV-03, FR-JOB-04, FR-JOB-05,
FR-JOB-06, P305).

Every page job in this package has the same skeleton: fetch one page,
ingest it, advance the cursor. Schema drift is the one failure mode they
all handle identically -- it is a known, named condition (INT-02), not a
bug to crash the job over, so the page is quarantined in the exception
queue as `needs_human` (with a reference to the raw snapshot saved before
the drift raised) and SKIPPED, while the cursor still advances so one
drifted page cannot stall the rest of an import forever."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .schema_drift import SchemaDriftDetected


def page_cursor(next_page: int, total_pages: int | None) -> dict[str, Any]:
    """The cursor half of a page result: where the next attempt resumes,
    and whether the source says this was the last page. An absent
    `totalPages` is never assumed to mean "done" (INV-11)."""
    return {"next_page": next_page + 1, "done": total_pages is not None and next_page >= total_pages}


async def quarantine_schema_drift(conn: AsyncConnection, job: Job, drift_exc: SchemaDriftDetected, *, source: str) -> int:
    record = await enqueue_exception(
        conn,
        source=source,
        exception_type="schema_drift",
        category="needs_human",
        reason=str(drift_exc),
        correlation_id=job.correlation_id,
        raw_ref=drift_exc.raw_snapshot_id,
        contract_name=drift_exc.contract_name,
    )
    return record.id


async def ingest_signal_page(
    conn: AsyncConnection,
    job: Job,
    ingest: Callable[[], Awaitable[list[int]]],
    *,
    source: str,
    cursor: dict[str, Any],
) -> dict[str, Any]:
    """Runs a signal-producing page ingest under the shared drift
    quarantine, and returns the job result: the already-computed `cursor`
    plus the signal ids stored (empty, with the quarantine record's id, if
    the page drifted)."""
    try:
        signal_ids = await ingest()
    except SchemaDriftDetected as drift_exc:
        exception_queue_id = await quarantine_schema_drift(conn, job, drift_exc, source=source)
        return {**cursor, "signal_ids": [], "exception_queue_id": exception_queue_id}

    return {**cursor, "signal_ids": signal_ids}
