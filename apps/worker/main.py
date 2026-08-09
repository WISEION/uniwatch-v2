"""Standalone worker process (NFR-ARC-03): claims durable jobs and runs
them to completion or terminal failure. No long-running network/IO ever
happens inside `apps/api` request handlers — it happens here instead
(FR-JOB-01)."""

from __future__ import annotations

import asyncio
import logging
import uuid
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncEngine

from packages.decision.decision_store import list_tenders_with_active_bid_decision
from packages.platform.correlation import bind_correlation_id
from packages.platform.db import get_engine
from packages.platform.egress.validator import EgressValidator
from packages.platform.jobs import Job, JobIdentity, JobStore, compute_backoff_seconds
from packages.platform.logging import configure_logging
from packages.platform.settings import get_settings
from packages.tender import etender_connector
from packages.tender import post_submission_tracking_job as tender_change_check_job
from packages.tender.change_tracking_store import list_tenders_due_for_check

from . import example_job

logger = logging.getLogger("uniwatch.worker")

LEASE_SECONDS = 30

# Owner decision, 2026-08-09 -- no source document supplies a re-check
# cadence for post-submission tracking (TENDER_INTELLIGENCE_SPEC.md's
# section 7.2 names the mechanism, not a poll interval); recorded in
# docs/decisions/OPEN-QUESTIONS.md as a deviation/assumption rather than a
# TBD-nn/D-nn number (hard ban #2 only covers those tagged literals).
TENDER_WATCH_POLL_INTERVAL_HOURS = 6


def _now_iso() -> str:
    return datetime.now(UTC).isoformat()


def get_egress_validator() -> EgressValidator:
    """Same construction already used at every other real (non-test) call
    site that needs a live validator (e.g. tests/security/test_*_live_fetch.py
    mirror production usage here): no resolver override, so it uses the
    real DNS resolver (packages/platform/egress/validator.py's
    default_resolver)."""
    return EgressValidator()


async def _process_claimed_job(engine: AsyncEngine, store: JobStore, job: Job, worker_id: str) -> None:
    # Correlation id is bound per job, threading API -> worker -> outbox
    # logs (NFR-OBS-01): the job's own correlation_id column was set at
    # enqueue time from whatever created it (e.g. the API request).
    bind_correlation_id(job.correlation_id)
    logger.info("claimed job %s (%s)", job.id, job.job_type)

    try:
        if job.job_type == example_job.JOB_TYPE:
            done = job.checkpoint.get("done", False)
            while not done:
                async with engine.begin() as conn:
                    current = await store.get(conn, job.id)
                    assert current is not None, f"job {job.id} vanished mid-processing (jobs are never deleted)"
                    checkpoint = await example_job.process_page(conn, current)
                    await store.checkpoint(conn, job.id, worker_id, checkpoint)
                done = checkpoint["done"]
        elif job.job_type == tender_change_check_job.JOB_TYPE:
            async with engine.begin() as conn:
                current = await store.get(conn, job.id)
                assert current is not None, f"job {job.id} vanished mid-processing (jobs are never deleted)"
                # get_egress_validator() is called lazily INSIDE each lambda,
                # not eagerly here -- so a test that monkeypatches
                # check_tender_for_changes itself (never invoking these
                # lambdas) never needs a real validator/settings/network.
                await tender_change_check_job.check_tender_for_changes(
                    conn,
                    tender_id=current.params["tender_id"],
                    fetch_event_details=lambda event_id: etender_connector.fetch_event_details_live(
                        conn, get_egress_validator(), event_id=event_id
                    ),
                    fetch_bom_page=lambda event_id, page_number: etender_connector.fetch_bom_lines_page_live(
                        conn, get_egress_validator(), event_id=event_id, page_number=page_number
                    ),
                    correlation_id=current.correlation_id,
                    observed_at=_now_iso(),
                )
                await store.checkpoint(conn, job.id, worker_id, {"done": True})
        else:
            raise ValueError(f"unknown job_type: {job.job_type}")

        async with engine.begin() as conn:
            await store.complete(conn, job.id, worker_id)
        logger.info("completed job %s", job.id)
    except Exception as exc:
        logger.exception("job %s failed", job.id)
        async with engine.begin() as conn:
            current = await store.get(conn, job.id)
            assert current is not None, f"job {job.id} vanished mid-processing (jobs are never deleted)"
            backoff = compute_backoff_seconds(current.attempt + 1)
            await store.fail_retry(conn, job.id, worker_id, error=str(exc), backoff_seconds=backoff)


async def run_once(engine: AsyncEngine, store: JobStore, worker_id: str) -> bool:
    """Claims and fully processes at most one job. Returns True if a job
    was claimed, False if the queue was empty."""
    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)
    if job is None:
        return False
    await _process_claimed_job(engine, store, job, worker_id)
    return True


async def enqueue_due_tender_checks(engine: AsyncEngine) -> int:
    """Enqueues one `tender_change_check` job per tender that (a) has an
    active bid/conditional_bid decision and (b) is due per
    `tender_watch_state`'s own last-checked timestamp -- called once per
    `run_forever` outer loop iteration (never per claimed job), so this is
    cheap-but-frequent against a timestamp gate rather than a spammy
    per-job side effect."""
    async with engine.begin() as conn:
        tracked = await list_tenders_with_active_bid_decision(conn)
        due = await list_tenders_due_for_check(
            conn, tender_ids=tracked, now=_now_iso(), interval_hours=TENDER_WATCH_POLL_INTERVAL_HOURS
        )
        store = JobStore()
        for tender_id in due:
            await store.enqueue(
                conn,
                JobIdentity(
                    job_type=tender_change_check_job.JOB_TYPE,
                    params={"tender_id": tender_id},
                    source="etender",
                    range_start=None,
                    range_end=None,
                    contract_version="etender.event_details",
                    correlation_id=f"tender-watch-{tender_id}",
                ),
            )
    return len(due)


async def run_forever(engine: AsyncEngine, worker_id: str | None = None, poll_interval: float = 1.0) -> None:
    worker_id = worker_id or f"worker-{uuid.uuid4()}"
    store = JobStore()
    logger.info("worker %s starting", worker_id)
    while True:
        await enqueue_due_tender_checks(engine)
        claimed = await run_once(engine, store, worker_id)
        if not claimed:
            await asyncio.sleep(poll_interval)


def main() -> None:
    configure_logging()
    settings = get_settings()
    engine = get_engine(settings.database_url)
    asyncio.run(run_forever(engine))


if __name__ == "__main__":
    main()
