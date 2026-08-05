"""Resumable World Bank donor-pipeline pagination (INV-03, FR-JOB-04,
FR-JOB-05, FR-JOB-06). Mirrors bom_lines_job.py's exact shape:
`process_worldbank_pipeline_page` processes exactly one page, resuming
from `job.checkpoint["next_os"]` (0 if never started).

`fetch_page` is an injected dependency, same reason as bom_lines_job.py's
own injection: tests can run against real captured fixtures without a
live network call. Unlike bom_lines_job.py (written in task 1.B, before
1.C's egress validator existed), a real implementation of `fetch_page`
using the egress validator is wired at the apps/worker layer, not deferred
-- see fetch_donor_pipeline_page_live in worldbank_connector.py."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.jobs import Job

from .page_job import ingest_signal_page
from .worldbank_connector import ingest_donor_pipeline_page

JOB_TYPE = "worldbank_donor_pipeline_page_fetch"

FetchPage = Callable[[str, int, int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_worldbank_pipeline_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    countrycode_exact = job.params["countrycode_exact"]
    rows = job.params["rows"]
    next_os = job.checkpoint.get("next_os", 0)

    raw_body, payload = await fetch_page(countrycode_exact, rows, next_os)

    async def ingest() -> list[int]:
        return await ingest_donor_pipeline_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            os_=next_os,
            correlation_id=job.correlation_id,
            observed_at=observed_at,
        )

    # Offset cursor, not a page number: this source pages by `os` (offset)
    # and reports a total row count, so `done` compares offsets.
    cursor = {"next_os": next_os + rows, "done": next_os + rows >= int(payload["total"])}
    return await ingest_signal_page(conn, job, ingest, source="worldbank_projects_api", cursor=cursor)
