"""Resumable pagination over eTender's own procurement-plan list endpoint
(INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06). Mirrors design_tender_job.py's
exact shape."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .etender_connector import ingest_procurement_plan_page
from .schema_drift import SchemaDriftDetected

JOB_TYPE = "etender_procurement_plan_page_fetch"

FetchPage = Callable[[int, int, str], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_procurement_plan_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    year = job.params["year"]
    buyer_organization_name = job.params.get("buyer_organization_name", "")
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(year, next_page, buyer_organization_name)

    try:
        signal_ids = await ingest_procurement_plan_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            year=year,
            page_number=next_page,
            buyer_organization_name=buyer_organization_name,
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
