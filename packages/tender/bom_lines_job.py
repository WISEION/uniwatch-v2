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

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .boq_completeness import record_page_fetched
from .etender_connector import SchemaDriftDetected, ingest_bom_lines_page
from .raw_snapshot import checksum_of

JOB_TYPE = "etender_bom_lines_page_fetch"

FetchPage = Callable[[int, int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_bom_lines_page(conn: AsyncConnection, job: Job, fetch_page: FetchPage) -> dict[str, Any]:
    event_id = job.params["event_id"]
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(event_id, next_page)

    try:
        version = await ingest_bom_lines_page(
            conn,
            event_id=event_id,
            raw_body=raw_body,
            payload=payload,
            correlation_id=job.correlation_id,
        )
    except SchemaDriftDetected as drift_exc:
        exception_record = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason=str(drift_exc),
            correlation_id=job.correlation_id,
            raw_ref=drift_exc.raw_snapshot_id,
            contract_name=drift_exc.contract_name,
        )
        total_pages = payload.get("totalPages")
        done = total_pages is not None and next_page >= total_pages
        return {
            "next_page": next_page + 1,
            "done": done,
            "tender_version_id": None,
            "boq_status": None,
            "exception_queue_id": exception_record.id,
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

    total_pages = payload.get("totalPages")
    done = total_pages is not None and next_page >= total_pages

    return {
        "next_page": next_page + 1,
        "done": done,
        "tender_version_id": version.id,
        "boq_status": boq_status.status,
    }
