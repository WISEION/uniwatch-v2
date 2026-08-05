"""Resumable pagination over eTender's own procurement-plan list endpoint
(INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06). Mirrors design_tender_job.py's
exact shape."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.jobs import Job

from .etender_connector import ingest_procurement_plan_page
from .page_job import ingest_signal_page, page_cursor

JOB_TYPE = "etender_procurement_plan_page_fetch"

FetchPage = Callable[[int, int, str], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_procurement_plan_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    year = job.params["year"]
    buyer_organization_name = job.params.get("buyer_organization_name", "")
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(year, next_page, buyer_organization_name)

    async def ingest() -> list[int]:
        return await ingest_procurement_plan_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            year=year,
            page_number=next_page,
            buyer_organization_name=buyer_organization_name,
            correlation_id=job.correlation_id,
            observed_at=observed_at,
        )

    return await ingest_signal_page(conn, job, ingest, source="etender", cursor=page_cursor(next_page, payload.get("totalPages")))
