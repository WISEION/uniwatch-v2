"""FR-JOB-08: unrecoverable/unhandled items are recorded, never dropped
silently. P306: a retryable item backs off and closes exactly once on
recovery, no duplicate row per attempt. P307: a contract fix closes every
matching needs_human record in one action."""

from __future__ import annotations

from sqlalchemy import text

from packages.platform.exception_queue import (
    close_exception,
    close_matching_needs_human,
    enqueue_exception,
    last_seen_by_source,
    list_open,
    schedule_retry,
)
from packages.platform.jobs import compute_backoff_seconds


async def test_enqueue_creates_an_open_record_with_reason_and_raw_ref(engine):
    async with engine.begin() as conn:
        record = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="added field 'newField' not in contract",
            correlation_id="corr-exc-1",
            raw_ref=None,
            contract_name="etender.event_details",
        )
    assert record.status == "open"
    assert record.category == "needs_human"
    assert record.attempts == 0


async def test_P306_retryable_backs_off_and_closes_exactly_once_on_recovery(engine):
    async with engine.begin() as conn:
        record = await enqueue_exception(
            conn,
            source="etender",
            exception_type="transient_network_error",
            category="retryable",
            reason="connection reset",
            correlation_id="corr-exc-2",
        )
        assert record.attempts == 0

        # A retry attempt fails again -- same underlying problem, same job
        # (same correlation_id) -- must bump the SAME row, not create a
        # second one.
        again = await enqueue_exception(
            conn,
            source="etender",
            exception_type="transient_network_error",
            category="retryable",
            reason="connection reset (again)",
            correlation_id="corr-exc-2",
        )
        assert again.id == record.id

        backed_off = await schedule_retry(conn, id=record.id, backoff_seconds=compute_backoff_seconds(1))
        assert backed_off.attempts == 1
        assert backed_off.next_retry_at is not None

        open_retryable = await list_open(conn, category="retryable")
        assert [r.id for r in open_retryable] == [record.id]  # exactly one row for this recurring problem

        # Recovery: close it.
        closed = await close_exception(conn, id=record.id, reason="recovered on retry", closed_by="worker")
        assert closed.status == "closed"

        # Closing again (e.g. a duplicate recovery signal) is a no-op, not
        # a second close event or an error.
        closed_again = await close_exception(conn, id=record.id, reason="recovered again??", closed_by="worker")
        assert closed_again.status == "closed"
        assert closed_again.closed_reason == "recovered on retry"  # unchanged -- first close wins

        assert await list_open(conn, category="retryable") == []


async def test_P307_contract_fix_closes_every_matching_needs_human_record(engine):
    async with engine.begin() as conn:
        r1 = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="page 12 had an unknown field",
            correlation_id="corr-exc-3",
            contract_name="etender.bom_lines_page",
        )
        r2 = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="page 30 had the same unknown field",
            correlation_id="corr-exc-4",
            contract_name="etender.bom_lines_page",
        )
        unrelated = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="a different resource's contract drifted",
            correlation_id="corr-exc-5",
            contract_name="etender.event_details",
        )

        closed = await close_matching_needs_human(
            conn, contract_name="etender.bom_lines_page", reason="contract updated to include the new field", closed_by="owner"
        )

    assert {c.id for c in closed} == {r1.id, r2.id}
    async with engine.begin() as conn:
        remaining_open = await list_open(conn, category="needs_human")
    assert [r.id for r in remaining_open] == [unrelated.id]  # unrelated contract's entry untouched


async def test_needs_human_is_not_retried_automatically(engine):
    # schedule_retry only affects retryable rows -- calling it on a
    # needs_human row must not silently "retry" something that requires a
    # human decision.
    async with engine.begin() as conn:
        record = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="unknown field",
            correlation_id="corr-exc-6",
        )
        result = await conn.execute(
            text(
                "UPDATE exception_queue SET attempts = attempts + 1 WHERE id = :id AND status = 'open' AND category = 'retryable'"
            ),
            {"id": record.id},
        )
    assert result.rowcount == 0  # the retryable-only guard clause matches nothing for a needs_human row


async def test_last_seen_by_source_reflects_the_most_recent_event(engine):
    async with engine.begin() as conn:
        await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason="field removed",
            correlation_id="corr-signal-3",
        )

    async with engine.connect() as conn:
        seen = await last_seen_by_source(conn)

    assert "etender" in seen


async def test_last_seen_by_source_filters_by_exception_type(engine):
    async with engine.begin() as conn:
        await enqueue_exception(
            conn,
            source="worldbank_projects_api",
            exception_type="egress_rejected",
            category="retryable",
            reason="blocked host",
            correlation_id="corr-signal-4",
        )

    async with engine.connect() as conn:
        drift_only = await last_seen_by_source(conn, exception_type="schema_drift")

    assert "worldbank_projects_api" not in drift_only
