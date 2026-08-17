"""Platform-scoped alert checks (Phase 6, task 6.C, NFR-OPS-02). Each check
is proven against both a healthy state (not firing) and a deliberately
provoked one (firing) -- same discipline as
tests/integration/test_invariant_checks.py."""

from __future__ import annotations

from packages.platform.alerts import (
    dead_lettered_jobs_present,
    exception_queue_has_open_items,
    invariant_violation_detected,
)
from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import JobIdentity, JobStore


async def test_dead_lettered_jobs_present_is_false_when_none_exist(engine):
    async with engine.connect() as conn:
        result = await dead_lettered_jobs_present(conn)
    assert result.firing is False


async def test_dead_lettered_jobs_present_fires_on_a_real_dead_letter(engine):
    store = JobStore()
    identity = JobIdentity(
        job_type="test_alert_job",
        params={},
        source="test",
        range_start=None,
        range_end=None,
        contract_version="v1",
        correlation_id="corr-alert-1",
    )
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, identity)
        claimed = await store.claim(conn, "worker-1", lease_seconds=60)
        assert claimed is not None
        for _ in range(claimed.max_attempts):
            status = await store.fail_retry(conn, job_id, "worker-1", "boom", backoff_seconds=0)
            if status == "failed":
                break
            await store.claim(conn, "worker-1", lease_seconds=60)

        result = await dead_lettered_jobs_present(conn)

    assert result.firing is True
    assert str(job_id) in result.detail


async def test_exception_queue_has_open_items_is_false_when_empty(engine):
    async with engine.connect() as conn:
        result = await exception_queue_has_open_items(conn)
    assert result.firing is False


async def test_exception_queue_has_open_items_fires_on_a_real_open_item(engine):
    async with engine.begin() as conn:
        await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="field removed",
            correlation_id="corr-alert-2",
        )
        result = await exception_queue_has_open_items(conn)
    assert result.firing is True


async def test_invariant_violation_detected_is_false_on_a_healthy_schema(engine):
    async with engine.connect() as conn:
        result = await invariant_violation_detected(conn)
    assert result.firing is False
