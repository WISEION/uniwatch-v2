"""P305: a schema-drift response is recorded in the exception queue as
needs_human (with a raw evidence reference) and the pagination job
continues past it instead of crashing -- one bad page must not stall a
42-page BOQ import forever."""

from __future__ import annotations

import json

from source_fixtures import ETENDER_FIXTURES
from sqlalchemy import text

from packages.platform.exception_queue import list_open
from packages.platform.jobs import JobIdentity, JobStore
from packages.tender.bom_lines_job import process_bom_lines_page

LEASE_SECONDS = 30


def _identity(**overrides) -> JobIdentity:
    base = {
        "job_type": "etender_bom_lines_page_fetch",
        "params": {"event_id": 355920},
        "source": "etender",
        "range_start": None,
        "range_end": None,
        "contract_version": "etender.bom_lines_page",
        "correlation_id": "corr-drift-job-1",
    }
    base.update(overrides)
    return JobIdentity(**base)


async def test_P305_drift_page_goes_to_exception_queue_and_pipeline_continues(engine):
    raw_body = (ETENDER_FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    drifted_payload = {**payload}
    del drifted_payload["totalItems"]  # simulate the source silently dropping a field

    async def drifted_fetch_page(event_id: int, page_number: int) -> tuple[bytes, dict]:
        return raw_body, drifted_payload

    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())
        await store.claim(conn, worker_id="w1", lease_seconds=LEASE_SECONDS)

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        checkpoint = await process_bom_lines_page(conn, job, drifted_fetch_page)
        await store.checkpoint(conn, job_id, "w1", checkpoint)

    # The job did NOT crash/raise -- it produced a checkpoint and moved on.
    assert checkpoint["tender_version_id"] is None
    assert checkpoint["boq_status"] is None
    assert checkpoint["next_page"] == 2  # advanced past the bad page, not stuck on page 1

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        # Raw evidence for the drifted response was still saved (etender_connector
        # always saves before checking drift).
        raw_row = (
            (await conn.execute(text("SELECT count(*) AS n FROM raw_snapshots WHERE correlation_id = 'corr-drift-job-1'")))
            .mappings()
            .one()
        )
        open_exceptions = await list_open(conn, category="needs_human")

    assert job.checkpoint["next_page"] == 2
    assert raw_row["n"] == 1
    assert len(open_exceptions) == 1
    exc = open_exceptions[0]
    assert exc.exception_type == "schema_drift"
    assert exc.contract_name == "etender.bom_lines_page"
    assert exc.raw_ref is not None
    assert exc.correlation_id == "corr-drift-job-1"


async def test_P305_repeated_drift_on_retry_does_not_duplicate_the_queue_entry(engine):
    raw_body = (ETENDER_FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    drifted_payload = {**payload}
    del drifted_payload["totalItems"]

    async def drifted_fetch_page(event_id: int, page_number: int) -> tuple[bytes, dict]:
        return raw_body, drifted_payload

    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity(correlation_id="corr-drift-job-2"))
        await store.claim(conn, worker_id="w1", lease_seconds=LEASE_SECONDS)

    # Same job (same correlation_id) processes what it thinks is the "next"
    # page twice in a row (e.g. a retry after some unrelated hiccup) --
    # still only one open exception-queue entry for this recurring drift.
    for _ in range(2):
        async with engine.begin() as conn:
            job = await store.get(conn, job_id)
            checkpoint = await process_bom_lines_page(conn, job, drifted_fetch_page)
            await store.checkpoint(conn, job_id, "w1", checkpoint)

    async with engine.begin() as conn:
        open_exceptions = await list_open(conn, category="needs_human")
    matching = [e for e in open_exceptions if e.correlation_id == "corr-drift-job-2"]
    assert len(matching) == 1
