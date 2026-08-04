"""Standalone worker process (NFR-ARC-03): claims durable jobs and runs
them to completion or terminal failure. No long-running network/IO ever
happens inside `apps/api` request handlers — it happens here instead
(FR-JOB-01)."""

from __future__ import annotations

import asyncio
import logging
import uuid

from sqlalchemy.ext.asyncio import AsyncEngine

from packages.platform.correlation import bind_correlation_id
from packages.platform.db import get_engine
from packages.platform.jobs import Job, JobStore, compute_backoff_seconds
from packages.platform.logging import configure_logging
from packages.platform.settings import get_settings

from . import example_job

logger = logging.getLogger("uniwatch.worker")

LEASE_SECONDS = 30


async def _process_claimed_job(
    engine: AsyncEngine, store: JobStore, job: Job, worker_id: str
) -> None:
    # Correlation id is bound per job, threading API -> worker -> outbox
    # logs (NFR-OBS-01): the job's own correlation_id column was set at
    # enqueue time from whatever created it (e.g. the API request).
    bind_correlation_id(job.correlation_id)
    logger.info("claimed job %s (%s)", job.id, job.job_type)

    try:
        if job.job_type != example_job.JOB_TYPE:
            raise ValueError(f"unknown job_type: {job.job_type}")

        done = job.checkpoint.get("done", False)
        while not done:
            async with engine.begin() as conn:
                current = await store.get(conn, job.id)
                checkpoint = await example_job.process_page(conn, current)
                await store.checkpoint(conn, job.id, worker_id, checkpoint)
            done = checkpoint["done"]

        async with engine.begin() as conn:
            await store.complete(conn, job.id, worker_id)
        logger.info("completed job %s", job.id)
    except Exception as exc:  # noqa: BLE001 - any failure here means retry/terminal-fail
        logger.exception("job %s failed", job.id)
        async with engine.begin() as conn:
            current = await store.get(conn, job.id)
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


async def run_forever(
    engine: AsyncEngine, worker_id: str | None = None, poll_interval: float = 1.0
) -> None:
    worker_id = worker_id or f"worker-{uuid.uuid4()}"
    store = JobStore()
    logger.info("worker %s starting", worker_id)
    while True:
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
