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

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .etender_connector import ingest_design_tender_signals_page
from .schema_drift import SchemaDriftDetected

JOB_TYPE = "etender_design_tender_page_fetch"

FetchPage = Callable[[dict[str, Any], int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_design_tender_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    query_params = job.params["query_params"]
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(query_params, next_page)

    try:
        signal_ids = await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=query_params,
            correlation_id=job.correlation_id,
            observed_at=observed_at,
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
        return {
            "next_page": next_page + 1,
            "done": total_pages is not None and next_page >= total_pages,
            "signal_ids": [],
            "exception_queue_id": exception_record.id,
        }

    total_pages = payload.get("totalPages")
    return {
        "next_page": next_page + 1,
        "done": total_pages is not None and next_page >= total_pages,
        "signal_ids": signal_ids,
    }
