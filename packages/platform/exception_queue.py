"""Exception queue (FR-JOB-08): anything that doesn't clear the happy path
-- schema drift, egress blocks, stale facts, unrecognized artifacts -- is
recorded here with a reason and (where one exists) a raw-evidence
reference, never dropped silently. `retryable` items get automatic
backoff (reusing `packages.platform.jobs.compute_backoff_seconds`);
`needs_human` items wait for an explicit close, whether from a human or
from an automated action like a contract fix (`close_matching_needs_human`,
P307). The table survives a worker restart because it's an ordinary table,
not in-memory state."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = """id, source, exception_type, category, raw_ref, contract_name,
              reason, correlation_id, attempts, next_retry_at, status,
              closed_reason, closed_by"""


@dataclass(frozen=True)
class ExceptionRecord:
    id: int
    source: str
    exception_type: str
    category: str
    raw_ref: int | None
    contract_name: str | None
    reason: str
    correlation_id: str
    attempts: int
    next_retry_at: object | None
    status: str
    closed_reason: str | None
    closed_by: str | None


def _row_to_record(row) -> ExceptionRecord:
    return ExceptionRecord(
        id=row["id"],
        source=row["source"],
        exception_type=row["exception_type"],
        category=row["category"],
        raw_ref=row["raw_ref"],
        contract_name=row["contract_name"],
        reason=row["reason"],
        correlation_id=row["correlation_id"],
        attempts=row["attempts"],
        next_retry_at=row["next_retry_at"],
        status=row["status"],
        closed_reason=row["closed_reason"],
        closed_by=row["closed_by"],
    )


async def enqueue_exception(
    conn: AsyncConnection,
    *,
    source: str,
    exception_type: str,
    category: str,
    reason: str,
    correlation_id: str,
    raw_ref: int | None = None,
    contract_name: str | None = None,
) -> ExceptionRecord:
    """Get-or-create by (source, exception_type, correlation_id): a retry of
    the same job's same problem bumps the existing open row rather than
    piling up a new row per attempt."""
    existing = (
        (
            await conn.execute(
                text(
                    f"""
                    SELECT {_COLUMNS} FROM exception_queue
                    WHERE source = :source AND exception_type = :exception_type
                      AND correlation_id = :correlation_id AND status = 'open'
                    """
                ),
                {"source": source, "exception_type": exception_type, "correlation_id": correlation_id},
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return _row_to_record(existing)

    row = (
        (
            await conn.execute(
                text(
                    f"""
                    INSERT INTO exception_queue
                        (source, exception_type, category, raw_ref, contract_name, reason, correlation_id)
                    VALUES (:source, :exception_type, :category, :raw_ref, :contract_name, :reason, :correlation_id)
                    RETURNING {_COLUMNS}
                    """
                ),
                {
                    "source": source,
                    "exception_type": exception_type,
                    "category": category,
                    "raw_ref": raw_ref,
                    "contract_name": contract_name,
                    "reason": reason,
                    "correlation_id": correlation_id,
                },
            )
        )
        .mappings()
        .one()
    )
    return _row_to_record(row)


async def list_open(conn: AsyncConnection, *, category: str | None = None) -> list[ExceptionRecord]:
    if category is None:
        rows = (
            (await conn.execute(text(f"SELECT {_COLUMNS} FROM exception_queue WHERE status = 'open' ORDER BY first_seen_at")))
            .mappings()
            .all()
        )
    else:
        rows = (
            (
                await conn.execute(
                    text(
                        f"""
                        SELECT {_COLUMNS} FROM exception_queue
                        WHERE status = 'open' AND category = :category ORDER BY first_seen_at
                        """
                    ),
                    {"category": category},
                )
            )
            .mappings()
            .all()
        )
    return [_row_to_record(row) for row in rows]


async def schedule_retry(conn: AsyncConnection, *, id: int, backoff_seconds: int) -> ExceptionRecord:
    """Retryable items only: bump `attempts`, push `next_retry_at` out by
    `backoff_seconds`. Does not touch `needs_human` semantics -- calling
    this on a needs_human row is a caller error, not silently allowed."""
    row = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE exception_queue
                    SET attempts = attempts + 1,
                        next_retry_at = now() + make_interval(secs => :backoff_seconds),
                        updated_at = now()
                    WHERE id = :id AND status = 'open' AND category = 'retryable'
                    RETURNING {_COLUMNS}
                    """
                ),
                {"id": id, "backoff_seconds": backoff_seconds},
            )
        )
        .mappings()
        .one()
    )
    return _row_to_record(row)


async def close_exception(conn: AsyncConnection, *, id: int, reason: str, closed_by: str) -> ExceptionRecord:
    """Idempotent: closing an already-closed record is a no-op that just
    returns its current (already-closed) state, not an error and not a
    second close event."""
    await conn.execute(
        text(
            """
            UPDATE exception_queue
            SET status = 'closed', closed_at = now(), closed_reason = :reason, closed_by = :closed_by, updated_at = now()
            WHERE id = :id AND status = 'open'
            """
        ),
        {"id": id, "reason": reason, "closed_by": closed_by},
    )
    row = (await conn.execute(text(f"SELECT {_COLUMNS} FROM exception_queue WHERE id = :id"), {"id": id})).mappings().one()
    return _row_to_record(row)


async def close_matching_needs_human(
    conn: AsyncConnection, *, contract_name: str, reason: str, closed_by: str
) -> list[ExceptionRecord]:
    """P307: fixing a contract closes every open needs_human record that
    names it, in one action -- not one-by-one."""
    rows = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE exception_queue
                    SET status = 'closed', closed_at = now(), closed_reason = :reason, closed_by = :closed_by, updated_at = now()
                    WHERE contract_name = :contract_name AND category = 'needs_human' AND status = 'open'
                    RETURNING {_COLUMNS}
                    """
                ),
                {"contract_name": contract_name, "reason": reason, "closed_by": closed_by},
            )
        )
        .mappings()
        .all()
    )
    return [_row_to_record(row) for row in rows]
