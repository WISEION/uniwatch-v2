"""Resumable pagination over eTender's own server-side Keyword=layihə
search (INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06). Mirrors bom_lines_job.py
and worldbank_pipeline_job.py's exact shape: `process_design_tender_page`
processes exactly one page, resuming from `job.checkpoint["next_page"]`
(1 if never started). Unlike scanning eTender's full unfiltered corpus,
this walks only the 147 real candidate tenders (15 real pages at
PageSize=10) the source's own search already narrowed down."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.jobs import Job

from .etender_connector import ingest_design_tender_signals_page
from .page_job import ingest_signal_page, page_cursor

JOB_TYPE = "etender_design_tender_page_fetch"

FetchPage = Callable[[dict[str, Any], int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_design_tender_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    query_params = job.params["query_params"]
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(query_params, next_page)

    async def ingest() -> list[int]:
        return await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=query_params,
            correlation_id=job.correlation_id,
            observed_at=observed_at,
        )

    return await ingest_signal_page(conn, job, ingest, source="etender", cursor=page_cursor(next_page, payload.get("totalPages")))
