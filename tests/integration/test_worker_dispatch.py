"""Task 4.B, task 6: proves the worker dispatch registry actually routes a
`tender_change_check` job to `post_submission_tracking_job.check_tender_for_changes`
(the FIRST real job-type dispatch alongside the `example_job` stub) --
`check_tender_for_changes` itself is stubbed out here so this test needs
no real eTender fetch and no real egress validator."""

from __future__ import annotations

import apps.worker.main as worker_main
from packages.platform.jobs import JobIdentity, JobStore
from packages.tender.post_submission_tracking_job import JOB_TYPE as TENDER_CHECK_JOB_TYPE


async def test_worker_dispatches_a_tender_change_check_job(engine, monkeypatch):
    calls = []

    async def fake_check_tender_for_changes(conn, *, tender_id, fetch_event_details, fetch_bom_page, correlation_id, observed_at):
        calls.append(tender_id)
        return {"change_detected": False, "change_type": None, "flagged_line_count": 0}

    # apps/worker/main.py imports the job module as `tender_change_check_job`
    # -- patch the attribute on that module object so the dispatch code
    # (which calls `tender_change_check_job.check_tender_for_changes(...)`)
    # picks up the stub without needing a real eTender fetch or a real
    # egress validator.
    monkeypatch.setattr(worker_main.tender_change_check_job, "check_tender_for_changes", fake_check_tender_for_changes)

    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(
            conn,
            JobIdentity(
                job_type=TENDER_CHECK_JOB_TYPE,
                params={"tender_id": 4242},
                source="etender",
                range_start=None,
                range_end=None,
                contract_version="etender.event_details",
                correlation_id="test-worker-dispatch-1",
            ),
        )

    claimed = await worker_main.run_once(engine, store, worker_id="test-worker-1")

    assert claimed is True
    assert calls == [4242]

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
    assert job.status == "completed"
