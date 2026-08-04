"""Example job type proving the worker mechanism end to end: identity,
resumable checkpoint, and an outbox event written in the same transaction
as the "page processed" effect (FR-JOB-01..03/07)."""

from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox
from packages.platform.jobs import Job

logger = logging.getLogger("uniwatch.worker.paged_echo")

JOB_TYPE = "paged_echo"


async def process_page(conn: AsyncConnection, job: Job) -> dict:
    """Processes exactly one page, resuming from `job.checkpoint['page']`
    (0 if never started). `conn` is the caller's own transactional
    connection, so the outbox row and the checkpoint update in
    `apps/worker/main.py` land in the same commit as this effect."""
    next_page = job.checkpoint.get("page", 0) + 1
    total_pages = job.params["total_pages"]

    logger.info("processing page %s/%s for job %s", next_page, total_pages, job.id)

    await outbox.enqueue(
        conn,
        aggregate_type="paged_echo_job",
        aggregate_id=str(job.id),
        event_type="page.processed",
        payload={"page": next_page, "total_pages": total_pages},
        correlation_id=job.correlation_id,
    )

    return {"page": next_page, "done": next_page >= total_pages}
