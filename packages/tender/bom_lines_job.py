"""Resumable BOM-lines pagination (INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06,
P002). `process_bom_lines_page` processes exactly one page, resuming from
`job.checkpoint["next_page"]` (1 if never started) -- mirrors
`apps/worker/example_job.py`'s pattern so the same durable-jobs mechanism
(`packages/platform/jobs.py`) drives it.

`fetch_page` is an injected dependency (`(event_id, page_number) ->
(raw_body, payload)`), deliberately not a real HTTP call here: real network
fetching is wired in once task 1.C's egress validator exists, so an
unvalidated live request is never hidden inside this ingestion mechanism.
Tests inject a fetch_page reading real captured fixtures.

If `fetch_page` raises, this function raises too, *before* calling
`store.checkpoint` -- so the caller's job-processing loop (see
`apps/worker/main.py`'s `_process_claimed_job` for the reference shape)
never advances the cursor for a page that didn't durably commit, and a
retry resumes at the exact same page (FR-JOB-04/05). A brand new job
identity (new `params`/`range`) always gets its own fresh row with
`checkpoint = {}`, so `next_page` naturally starts at 1 -- there is no
shared cursor for two different job identities to collide on (FR-JOB-06).

A schema-drift response is different: it is a known, named failure mode
(INT-02), not a bug to crash the job over. It is recorded in the exception
queue as `needs_human` (with a reference to the raw snapshot that was
already saved) and the page is SKIPPED -- `next_page` still advances, so
one drifted page does not stall the rest of a 42-page BOQ import forever
(P305). The BOQ completeness status still reflects reality (that page's
lines are simply not counted as stored)."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.jobs import Job

from .boq_completeness import record_page_fetched
from .boq_line_model import build_boq_lines
from .boq_lines_store import store_boq_lines
from .etender_connector import ingest_bom_lines_page
from .page_job import page_cursor, quarantine_schema_drift
from .raw_snapshot import checksum_of
from .schema_drift import SchemaDriftDetected

JOB_TYPE = "etender_bom_lines_page_fetch"

FetchPage = Callable[[int, int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_bom_lines_page(conn: AsyncConnection, job: Job, fetch_page: FetchPage) -> dict[str, Any]:
    event_id = job.params["event_id"]
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(event_id, next_page)
    cursor = page_cursor(next_page, payload.get("totalPages"))

    try:
        version = await ingest_bom_lines_page(
            conn,
            event_id=event_id,
            raw_body=raw_body,
            payload=payload,
            correlation_id=job.correlation_id,
        )
    except SchemaDriftDetected as drift_exc:
        return {
            **cursor,
            "tender_version_id": None,
            "boq_status": None,
            "exception_queue_id": await quarantine_schema_drift(conn, job, drift_exc, source="etender"),
            "boq_lines_stored": 0,
        }

    boq_status = await record_page_fetched(
        conn,
        source="etender",
        event_id=event_id,
        page_number=next_page,
        lines_on_page=payload["itemsInPage"],
        expected_total=payload.get("totalItems"),
        expected_pages=payload.get("totalPages"),
        page_checksum=checksum_of(raw_body),
    )

    lines = build_boq_lines(page_number=next_page, items=payload["items"])
    boq_lines_stored = await store_boq_lines(
        conn,
        source="etender",
        event_id=event_id,
        tender_version_id=version.id,
        raw_snapshot_id=version.raw_snapshot_id,
        lines=lines,
    )

    return {
        **cursor,
        "tender_version_id": version.id,
        "boq_status": boq_status.status,
        "boq_lines_stored": boq_lines_stored,
    }
