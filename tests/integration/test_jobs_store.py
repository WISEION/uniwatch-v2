"""FR-JOB-01, FR-JOB-02, FR-JOB-03, FR-JOB-04, FR-JOB-06, P002, P113, P116."""

from __future__ import annotations

from sqlalchemy import text

from packages.platform.jobs import JobIdentity, JobNotOwned, JobStore

import pytest


def _identity(**overrides) -> JobIdentity:
    base = dict(
        job_type="etender_page_fetch",
        params={"filter": "open"},
        source="etender",
        range_start="2026-01-01",
        range_end="2026-01-31",
        contract_version="v1",
        correlation_id="corr-jobs-1",
    )
    base.update(overrides)
    return JobIdentity(**base)


async def test_claim_returns_none_when_no_jobs(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id="w1", lease_seconds=30)
    assert job is None


async def test_enqueue_then_claim_returns_full_identity(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())

    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id="w1", lease_seconds=30)
    assert job.id == job_id
    assert job.job_type == "etender_page_fetch"
    assert job.params == {"filter": "open"}
    assert job.source == "etender"
    assert job.range_start == "2026-01-01"
    assert job.range_end == "2026-01-31"
    assert job.contract_version == "v1"
    assert job.correlation_id == "corr-jobs-1"
    assert job.status == "leased"
    assert job.lease_owner == "w1"
    assert job.checkpoint == {}


async def test_new_filter_or_range_is_a_separate_job_with_its_own_checkpoint(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_a_id = await store.enqueue(conn, _identity(range_start="2026-01-01", range_end="2026-01-31"))
        job_b_id = await store.enqueue(conn, _identity(range_start="2026-02-01", range_end="2026-02-28"))

    async with engine.begin() as conn:
        job_a = await store.claim(conn, worker_id="w1", lease_seconds=30)
        await store.checkpoint(conn, job_a.id, "w1", {"page": 5})

    async with engine.begin() as conn:
        job_b = await store.get(conn, job_b_id)
    assert {job_a_id} == {job_a.id}
    assert job_b.checkpoint == {}  # job B's cursor was never touched by job A's progress


async def test_two_concurrent_claims_do_not_get_the_same_job(engine, _database_url):
    from packages.platform.db import get_engine

    store = JobStore()
    async with engine.begin() as conn:
        job_1 = await store.enqueue(conn, _identity(range_start="p1"))
        job_2 = await store.enqueue(conn, _identity(range_start="p2"))

    engine_a = get_engine(_database_url)
    engine_b = get_engine(_database_url)
    try:
        conn_a = await engine_a.connect()
        conn_b = await engine_b.connect()
        try:
            txn_a = await conn_a.begin()
            txn_b = await conn_b.begin()
            try:
                claimed_a = await store.claim(conn_a, worker_id="worker-a", lease_seconds=30)
                claimed_b = await store.claim(conn_b, worker_id="worker-b", lease_seconds=30)
                assert {claimed_a.id, claimed_b.id} == {job_1, job_2}
            finally:
                await txn_a.commit()
                await txn_b.commit()
        finally:
            await conn_a.close()
            await conn_b.close()
    finally:
        await engine_a.dispose()
        await engine_b.dispose()


async def test_checkpoint_survives_simulated_worker_crash_and_resumes(engine):
    """FR-JOB-01..03, P113: a job whose lease expired (worker died before
    calling complete/fail_retry) is reclaimable by another worker and keeps
    the checkpoint the dead worker last wrote — resume, not restart."""
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())

    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id="worker-dead", lease_seconds=30)
        await store.checkpoint(conn, job.id, "worker-dead", {"page": 3, "rows_written": 150})

    # Simulate the crash: force the lease to already be expired, without the
    # worker ever calling complete()/fail_retry().
    async with engine.begin() as conn:
        await conn.execute(
            text("UPDATE jobs SET lease_expires_at = now() - interval '1 second' WHERE id = :id"),
            {"id": job_id},
        )

    async with engine.begin() as conn:
        resumed = await store.claim(conn, worker_id="worker-new", lease_seconds=30)
    assert resumed.id == job_id
    assert resumed.checkpoint == {"page": 3, "rows_written": 150}
    assert resumed.lease_owner == "worker-new"


async def test_cancel_prevents_further_claims(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())
        await store.cancel(conn, job_id)

    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id="w1", lease_seconds=30)
    assert job is None

    async with engine.begin() as conn:
        cancelled = await store.get(conn, job_id)
    assert cancelled.status == "cancelled"


async def test_fail_retry_schedules_backoff_then_becomes_reclaimable(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())

    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id="w1", lease_seconds=30)
        status = await store.fail_retry(conn, job.id, "w1", error="transient timeout", backoff_seconds=0)
    assert status == "pending"

    async with engine.begin() as conn:
        retried = await store.claim(conn, worker_id="w2", lease_seconds=30)
    assert retried.id == job_id
    assert retried.attempt == 1
    assert retried.last_error == "transient timeout"


async def test_fail_retry_exhausts_attempts_to_terminal_failed(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())
        await conn.execute(text("UPDATE jobs SET max_attempts = 1 WHERE id = :id"), {"id": job_id})

    async with engine.begin() as conn:
        job = await store.claim(conn, worker_id="w1", lease_seconds=30)
        status = await store.fail_retry(conn, job.id, "w1", error="permanent", backoff_seconds=0)
    assert status == "failed"

    async with engine.begin() as conn:
        final = await store.get(conn, job_id)
    assert final.status == "failed"

    async with engine.begin() as conn:
        reclaimed = await store.claim(conn, worker_id="w2", lease_seconds=30)
    assert reclaimed is None  # terminal failure is not reclaimable


async def test_heartbeat_by_non_owner_raises_job_not_owned(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())
        await store.claim(conn, worker_id="owner", lease_seconds=30)

    async with engine.begin() as conn:
        with pytest.raises(JobNotOwned):
            await store.heartbeat(conn, job_id, "not-the-owner", lease_seconds=30)


async def test_complete_marks_job_done_and_not_reclaimable(engine):
    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity())
        job = await store.claim(conn, worker_id="w1", lease_seconds=30)
        await store.complete(conn, job.id, "w1")

    async with engine.begin() as conn:
        done = await store.get(conn, job_id)
        assert done.status == "completed"
        again = await store.claim(conn, worker_id="w2", lease_seconds=30)
    assert again is None
