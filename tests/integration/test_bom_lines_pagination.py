"""INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06, P002: resumable BOM-lines
pagination. Cursor moves only after an atomic commit; a page fetch failure
does not skip ahead on retry; a new job identity always starts at page 1."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from packages.platform.jobs import JobIdentity, JobStore
from packages.tender.bom_lines_job import process_bom_lines_page
from packages.tender.raw_snapshot import checksum_of

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"

LEASE_SECONDS = 30


async def _load_page(event_id: int, page_number: int) -> tuple[bytes, dict]:
    assert event_id == 355920
    raw_body = (FIXTURES / f"event_355920_bomlines_page{page_number}.raw.json").read_bytes()
    return raw_body, json.loads(raw_body)


def _identity(**overrides) -> JobIdentity:
    base = {
        "job_type": "etender_bom_lines_page_fetch",
        "params": {"event_id": 355920},
        "source": "etender",
        "range_start": None,
        "range_end": None,
        "contract_version": "etender.bom_lines_page",
        "correlation_id": "corr-bom-job-1",
    }
    base.update(overrides)
    return JobIdentity(**base)


async def test_resumable_pagination_processes_real_pages_in_order(engine):
    store = JobStore()
    worker_id = "w1"
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())
        await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)

    for _ in range(3):
        async with engine.begin() as conn:
            job = await store.get(conn, job_id)
            checkpoint = await process_bom_lines_page(conn, job, _load_page)
            await store.checkpoint(conn, job_id, worker_id, checkpoint)

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        boq_row = (
            (await conn.execute(text("SELECT fetched_pages, stored_lines, status FROM boq_import WHERE event_id = 355920")))
            .mappings()
            .one()
        )
    assert job.checkpoint["next_page"] == 4
    assert boq_row["fetched_pages"] == 3
    assert boq_row["stored_lines"] == 300
    assert boq_row["status"] == "in_progress"


async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    store = JobStore()
    worker_id = "w1"
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity(correlation_id="corr-bom-job-2"))
        await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)

    attempts: list[int] = []

    async def flaky_fetch_page(event_id: int, page_number: int) -> tuple[bytes, dict]:
        attempts.append(page_number)
        if page_number == 2 and attempts.count(2) == 1:
            raise ConnectionError("simulated transient network failure on page 2")
        return await _load_page(event_id, page_number)

    # Page 1 succeeds.
    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        checkpoint = await process_bom_lines_page(conn, job, flaky_fetch_page)
        await store.checkpoint(conn, job_id, worker_id, checkpoint)
    assert checkpoint["next_page"] == 2

    # Page 2 fails -- job.checkpoint must NOT advance past page 2.
    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        try:
            await process_bom_lines_page(conn, job, flaky_fetch_page)
            raised = False
        except ConnectionError:
            raised = True
    assert raised is True

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
    assert job.checkpoint["next_page"] == 2  # unchanged -- did not skip to 3

    # Retry: page 2 now succeeds (real page-2 content, distinct from page 1/3).
    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        checkpoint = await process_bom_lines_page(conn, job, flaky_fetch_page)
        await store.checkpoint(conn, job_id, worker_id, checkpoint)
    assert checkpoint["next_page"] == 3

    async with engine.begin() as conn:
        boq_row = (
            (
                await conn.execute(
                    text("SELECT fetched_pages, page_checksums FROM boq_import WHERE event_id = 355920 AND source = 'etender'")
                )
            )
            .mappings()
            .one()
        )
    # Exactly one successful fetch of page 2 was recorded (not zero, not twice).
    assert boq_row["fetched_pages"] == 2
    page2_body = (FIXTURES / "event_355920_bomlines_page2.raw.json").read_bytes()
    page_checksums = boq_row["page_checksums"]
    if isinstance(page_checksums, str):
        page_checksums = json.loads(page_checksums)
    assert page_checksums["2"] == checksum_of(page2_body)

    # Page 3 fetched next -- proves no page was skipped or duplicated.
    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        checkpoint = await process_bom_lines_page(conn, job, flaky_fetch_page)
        await store.checkpoint(conn, job_id, worker_id, checkpoint)
    assert checkpoint["next_page"] == 4
    assert attempts == [1, 2, 2, 3]  # page 2 attempted twice, nothing else repeated or skipped


async def test_new_job_identity_starts_at_page_1_independently(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_a = await store.enqueue(conn, _identity(params={"event_id": 355920}, correlation_id="corr-a"))
        await store.claim(conn, worker_id="w1", lease_seconds=LEASE_SECONDS)

    # Advance job A to page 2.
    async with engine.begin() as conn:
        job = await store.get(conn, job_a)
        checkpoint = await process_bom_lines_page(conn, job, _load_page)
        await store.checkpoint(conn, job_a, "w1", checkpoint)

    # A second, distinct job identity (different correlation_id / a fresh
    # enqueue) for the SAME event must not inherit job A's cursor -- it is
    # a new job row with its own empty checkpoint (FR-JOB-06).
    async with engine.begin() as conn:
        job_b = await store.enqueue(conn, _identity(params={"event_id": 355920}, correlation_id="corr-b-new-range"))
        job_b_row = await store.get(conn, job_b)

    assert job_a != job_b
    assert job_b_row.checkpoint == {}
    assert job_b_row.checkpoint.get("next_page", 1) == 1


async def test_boq_lines_are_stored_for_every_real_page_processed(engine):
    store = JobStore()
    worker_id = "w1"
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity(correlation_id="corr-boq-lines-1"))
        await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)

    for _ in range(3):
        async with engine.begin() as conn:
            job = await store.get(conn, job_id)
            checkpoint = await process_bom_lines_page(conn, job, _load_page)
            assert checkpoint["boq_lines_stored"] == 100
            await store.checkpoint(conn, job_id, worker_id, checkpoint)

    async with engine.begin() as conn:
        total_lines = (
            (await conn.execute(text("SELECT count(*) AS n FROM boq_lines WHERE event_id = 355920"))).mappings().one()["n"]
        )
        every_line_has_unit_and_qty = (
            (
                await conn.execute(
                    text(
                        "SELECT count(*) AS n FROM boq_lines "
                        "WHERE event_id = 355920 AND (unit_raw IS NULL OR unit_raw = '' OR qty IS NULL)"
                    )
                )
            )
            .mappings()
            .one()["n"]
        )
    # P308 (real-data half): every real line across all 3 pages decomposed,
    # each with a non-null unit + qty.
    assert total_lines == 300
    assert every_line_has_unit_and_qty == 0


async def test_item_level_drift_skips_boq_lines_for_that_page_same_as_page_level_drift(engine):
    store = JobStore()
    worker_id = "w1"
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity(correlation_id="corr-boq-lines-drift"))
        await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)

    async def drifted_fetch_page(event_id: int, page_number: int) -> tuple[bytes, dict]:
        raw_body, payload = await _load_page(event_id, page_number)
        drifted = {
            **payload,
            "items": [{**payload["items"][0], "quantity": str(payload["items"][0]["quantity"])}, *payload["items"][1:]],
        }
        return raw_body, drifted

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        checkpoint = await process_bom_lines_page(conn, job, drifted_fetch_page)
        await store.checkpoint(conn, job_id, worker_id, checkpoint)

    assert checkpoint["boq_status"] is None  # same P305 skip-path as page-level drift
    assert checkpoint["next_page"] == 2  # pagination still advances, one drifted page doesn't stall the job

    async with engine.begin() as conn:
        lines_for_this_page = (
            (await conn.execute(text("SELECT count(*) AS n FROM boq_lines WHERE event_id = 355920 AND page_number = 1")))
            .mappings()
            .one()["n"]
        )
    assert lines_for_this_page == 0  # a page that failed drift-checking stores no guessed lines
