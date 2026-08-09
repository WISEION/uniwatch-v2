"""Task 4.B, task 6: proves the worker dispatch registry actually routes a
`tender_change_check` job to `post_submission_tracking_job.check_tender_for_changes`
(the FIRST real job-type dispatch alongside the `example_job` stub) --
`check_tender_for_changes` itself is stubbed out here so this test needs
no real eTender fetch and no real egress validator."""

from __future__ import annotations

import json
import logging

from sqlalchemy import text

import apps.worker.main as worker_main
from packages.decision.decision_model import Decision
from packages.decision.decision_store import store_decision
from packages.platform.jobs import JobIdentity, JobNotOwned, JobStore
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.post_submission_tracking_job import JOB_TYPE as TENDER_CHECK_JOB_TYPE
from packages.tender.raw_snapshot import save_raw_snapshot


async def test_worker_dispatches_a_tender_change_check_job(engine, monkeypatch):
    calls = []

    async def fake_check_tender_for_changes(
        conn, *, tender_id, fetch_event_details, fetch_bom_page, correlation_id, observed_at, heartbeat=None
    ):
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


async def test_enqueue_due_tender_checks_does_not_double_enqueue_a_still_pending_tender(engine):
    """Review-fix regression test: `list_tenders_due_for_check`'s gate is
    `tender_watch_state.last_checked_at`, which used to be written ONLY at
    job-completion time (inside `check_tender_for_changes`). Since
    `run_forever` calls `enqueue_due_tender_checks` every outer-loop
    iteration and `run_once` claims at most one job per call,
    `JobStore.enqueue`'s plain INSERT (no identity dedup) meant a tender
    whose job hadn't finished yet got re-enqueued on every single
    iteration. `enqueue_due_tender_checks` must now upsert
    `tender_watch_state` at ENQUEUE time so a second call immediately after
    the first sees the tender as no-longer-due."""
    async with engine.begin() as conn:
        raw_snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-worker-dispatch-dedup",
            raw_body=json.dumps({"eventId": 1}).encode("utf-8"),
            contract_version="v1",
            correlation_id="test-worker-dispatch-dedup",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-worker-dispatch-dedup")
        await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        await store_decision(
            conn,
            Decision(
                tender_id=tender_id,
                decision_type="bid",
                conditions=(),
                deadline=None,
                justification="test",
                actor="pm-1",
                decided_at="2026-08-09T00:00:00+00:00",
                go_no_go_inputs_id=None,
                bid_readiness_candidate_id=None,
            ),
        )

    first_enqueued = await worker_main.enqueue_due_tender_checks(engine)
    second_enqueued = await worker_main.enqueue_due_tender_checks(engine)

    assert first_enqueued == 1
    assert second_enqueued == 0

    async with engine.begin() as conn:
        job_count = (
            await conn.execute(
                text("SELECT count(*) FROM jobs WHERE job_type = :jt AND params->>'tender_id' = :tid"),
                {"jt": TENDER_CHECK_JOB_TYPE, "tid": str(tender_id)},
            )
        ).scalar_one()

    assert job_count == 1


async def test_run_once_does_not_crash_when_the_lease_was_already_reclaimed(engine, monkeypatch, caplog):
    """Final Review C1 regression test: if a job's lease is stolen by
    another worker mid-processing (e.g. a heartbeat lost a race, or the
    lease genuinely expired), `store.fail_retry`'s own `JobNotOwned`
    bookkeeping exception must NOT escape `_process_claimed_job` -- that
    would propagate through `run_once` and crash `run_forever`'s entire
    `while True` loop over what is really just a lease-ownership race, not
    a fatal worker error. The reclaiming worker owns recording this job's
    outcome now. Uses an unknown job_type to force the `except Exception`
    branch cheaply, without needing a real tender_change_check failure."""
    store = JobStore()
    async with engine.begin() as conn:
        await store.enqueue(
            conn,
            JobIdentity(
                job_type="an-unrecognized-job-type-to-force-the-except-branch",
                params={},
                source="test",
                range_start=None,
                range_end=None,
                contract_version="v1",
                correlation_id="test-worker-lease-race",
            ),
        )

    async def fake_fail_retry(*args, **kwargs):
        raise JobNotOwned(job_id=-1, worker_id="some-other-worker")

    monkeypatch.setattr(store, "fail_retry", fake_fail_retry)

    with caplog.at_level(logging.WARNING):
        claimed = await worker_main.run_once(engine, store, worker_id="test-worker-lease-race")

    assert claimed is True
    assert any("lease was already reclaimed" in record.message for record in caplog.records)
