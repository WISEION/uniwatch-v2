"""NFR-OBS-01: one correlation id threaded API (job creation) -> worker ->
outbox row."""

from __future__ import annotations

from sqlalchemy import text

from apps.worker.main import run_once
from packages.platform.correlation import get_correlation_id_or_none
from packages.platform.jobs import JobIdentity, JobStore


def _api_created_identity(correlation_id: str, total_pages: int) -> JobIdentity:
    """Stands in for what apps/api would build when a request enqueues a
    job — the correlation id here is the same one FastAPI's
    CorrelationIdMiddleware would have bound for that request."""
    return JobIdentity(
        job_type="paged_echo",
        params={"total_pages": total_pages},
        source="test-source",
        range_start=None,
        range_end=None,
        contract_version="v1",
        correlation_id=correlation_id,
    )


async def test_worker_processes_multi_page_job_and_propagates_correlation_id(engine):
    store = JobStore()
    correlation_id = "corr-from-api-request-42"

    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _api_created_identity(correlation_id, total_pages=3))

    claimed = await run_once(engine, store, worker_id="worker-1")
    assert claimed is True

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        outbox_rows = (
            await conn.execute(
                text(
                    "SELECT event_type, correlation_id, payload FROM outbox "
                    "WHERE aggregate_id = :id ORDER BY id"
                ),
                {"id": str(job_id)},
            )
        ).mappings().all()

    assert job.status == "completed"
    assert len(outbox_rows) == 3
    assert all(row["correlation_id"] == correlation_id for row in outbox_rows)
    assert [row["event_type"] for row in outbox_rows] == ["page.processed"] * 3


async def test_correlation_id_is_bound_in_worker_context_while_processing(engine):
    store = JobStore()
    correlation_id = "corr-bound-check"
    async with engine.begin() as conn:
        await store.enqueue(conn, _api_created_identity(correlation_id, total_pages=1))

    await run_once(engine, store, worker_id="worker-2")

    assert get_correlation_id_or_none() == correlation_id


async def test_empty_queue_returns_false(engine):
    store = JobStore()
    claimed = await run_once(engine, store, worker_id="worker-3")
    assert claimed is False


async def test_unknown_job_type_is_retried_not_silently_dropped(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(
            conn,
            JobIdentity(
                job_type="not_a_real_job_type",
                params={},
                source="test-source",
                range_start=None,
                range_end=None,
                contract_version="v1",
                correlation_id="corr-unknown-type",
            ),
        )

    claimed = await run_once(engine, store, worker_id="worker-4")
    assert claimed is True

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
    assert job.status == "pending"
    assert job.attempt == 1
    assert "unknown job_type" in job.last_error
