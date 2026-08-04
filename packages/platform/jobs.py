"""Durable worker jobs: full identity, lease, progress, retry with backoff,
cancel, resume (FR-JOB-01..03, P002, P113, P116).

A job's identity (`job_type`, `params`, `source`, `range_start`/`range_end`,
`contract_version`, `correlation_id`) is fixed at `enqueue` time and never
mutated — a new filter/range always gets a new job row with its own
`checkpoint`, so a cursor can never leak from one job identity to another
(FR-JOB-02, FR-JOB-06). `claim` uses `SELECT ... FOR UPDATE SKIP LOCKED` so
concurrent workers never claim the same row, and reclaims jobs whose lease
expired (the worker that held it died / was killed) without losing their
`checkpoint` — that reclaim is what makes a job survive a worker restart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class JobIdentity:
    job_type: str
    params: dict[str, Any]
    source: str
    range_start: str | None
    range_end: str | None
    contract_version: str
    correlation_id: str


@dataclass(frozen=True)
class Job:
    id: int
    job_type: str
    params: dict[str, Any]
    source: str
    range_start: str | None
    range_end: str | None
    contract_version: str
    correlation_id: str
    status: str
    lease_owner: str | None
    attempt: int
    max_attempts: int
    checkpoint: dict[str, Any]
    last_error: str | None


class JobNotOwned(Exception):
    def __init__(self, job_id: int, worker_id: str):
        super().__init__(f"job {job_id} is not currently leased by {worker_id!r}")
        self.job_id = job_id
        self.worker_id = worker_id


def compute_backoff_seconds(attempt: int, base_seconds: int = 2, cap_seconds: int = 300) -> int:
    """Skeleton default backoff schedule (exponential, capped) — not a
    TBD-tagged SLO number, just a mechanism placeholder attempt/retry logic
    can rely on having *some* deterministic schedule."""
    return min(cap_seconds, base_seconds**max(attempt, 1))


def _as_dict(value: Any) -> dict:
    return json.loads(value) if isinstance(value, str) else value


def _row_to_job(row) -> Job:
    return Job(
        id=row["id"],
        job_type=row["job_type"],
        params=_as_dict(row["params"]),
        source=row["source"],
        range_start=row["range_start"],
        range_end=row["range_end"],
        contract_version=row["contract_version"],
        correlation_id=row["correlation_id"],
        status=row["status"],
        lease_owner=row["lease_owner"],
        attempt=row["attempt"],
        max_attempts=row["max_attempts"],
        checkpoint=_as_dict(row["checkpoint"]),
        last_error=row["last_error"],
    )


_JOB_COLUMNS = """id, job_type, params, source, range_start, range_end, contract_version,
                  correlation_id, status, lease_owner, attempt, max_attempts, checkpoint, last_error"""


class JobStore:
    async def enqueue(self, conn: AsyncConnection, identity: JobIdentity) -> int:
        row = (
            await conn.execute(
                text(
                    """
                    INSERT INTO jobs
                        (job_type, params, source, range_start, range_end,
                         contract_version, correlation_id)
                    VALUES (:job_type, CAST(:params AS jsonb), :source, :range_start,
                            :range_end, :contract_version, :correlation_id)
                    RETURNING id
                    """
                ),
                {
                    "job_type": identity.job_type,
                    "params": json.dumps(identity.params),
                    "source": identity.source,
                    "range_start": identity.range_start,
                    "range_end": identity.range_end,
                    "contract_version": identity.contract_version,
                    "correlation_id": identity.correlation_id,
                },
            )
        ).first()
        return row[0]

    async def claim(self, conn: AsyncConnection, worker_id: str, lease_seconds: int) -> Job | None:
        selected = (
            await conn.execute(
                text(
                    """
                    SELECT id FROM jobs
                    WHERE (status = 'pending' AND (next_retry_at IS NULL OR next_retry_at <= now()))
                       OR (status = 'leased' AND lease_expires_at < now())
                    ORDER BY created_at ASC
                    LIMIT 1
                    FOR UPDATE SKIP LOCKED
                    """
                )
            )
        ).first()
        if selected is None:
            return None

        row = (
            await conn.execute(
                text(
                    f"""
                    UPDATE jobs
                    SET status = 'leased',
                        lease_owner = :worker_id,
                        lease_expires_at = now() + make_interval(secs => :lease_seconds),
                        updated_at = now()
                    WHERE id = :id
                    RETURNING {_JOB_COLUMNS}
                    """
                ),
                {"id": selected[0], "worker_id": worker_id, "lease_seconds": lease_seconds},
            )
        ).mappings().first()
        return _row_to_job(row)

    async def heartbeat(
        self, conn: AsyncConnection, job_id: int, worker_id: str, lease_seconds: int
    ) -> None:
        result = await conn.execute(
            text(
                """
                UPDATE jobs
                SET lease_expires_at = now() + make_interval(secs => :lease_seconds),
                    updated_at = now()
                WHERE id = :id AND lease_owner = :worker_id AND status = 'leased'
                """
            ),
            {"id": job_id, "worker_id": worker_id, "lease_seconds": lease_seconds},
        )
        if result.rowcount == 0:
            raise JobNotOwned(job_id, worker_id)

    async def checkpoint(
        self, conn: AsyncConnection, job_id: int, worker_id: str, checkpoint: dict
    ) -> None:
        """Called only after the data the checkpoint describes has already
        been durably committed by the caller (FR-JOB-04) — the checkpoint
        itself is just "where to resume from", never the trigger that makes
        data durable."""
        result = await conn.execute(
            text(
                """
                UPDATE jobs
                SET checkpoint = CAST(:checkpoint AS jsonb), updated_at = now()
                WHERE id = :id AND lease_owner = :worker_id AND status = 'leased'
                """
            ),
            {"id": job_id, "worker_id": worker_id, "checkpoint": json.dumps(checkpoint)},
        )
        if result.rowcount == 0:
            raise JobNotOwned(job_id, worker_id)

    async def complete(self, conn: AsyncConnection, job_id: int, worker_id: str) -> None:
        result = await conn.execute(
            text(
                """
                UPDATE jobs
                SET status = 'completed', lease_owner = NULL, lease_expires_at = NULL,
                    updated_at = now()
                WHERE id = :id AND lease_owner = :worker_id
                """
            ),
            {"id": job_id, "worker_id": worker_id},
        )
        if result.rowcount == 0:
            raise JobNotOwned(job_id, worker_id)

    async def fail_retry(
        self, conn: AsyncConnection, job_id: int, worker_id: str, error: str, backoff_seconds: int
    ) -> str:
        """Returns the resulting status: 'pending' (will be retried) or
        'failed' (attempts exhausted, terminal)."""
        row = (
            await conn.execute(
                text(
                    "SELECT attempt, max_attempts FROM jobs WHERE id = :id AND lease_owner = :worker_id"
                ),
                {"id": job_id, "worker_id": worker_id},
            )
        ).mappings().first()
        if row is None:
            raise JobNotOwned(job_id, worker_id)

        new_attempt = row["attempt"] + 1
        if new_attempt < row["max_attempts"]:
            await conn.execute(
                text(
                    """
                    UPDATE jobs
                    SET status = 'pending', attempt = :attempt, last_error = :error,
                        lease_owner = NULL, lease_expires_at = NULL,
                        next_retry_at = now() + make_interval(secs => :backoff),
                        updated_at = now()
                    WHERE id = :id
                    """
                ),
                {"id": job_id, "attempt": new_attempt, "error": error, "backoff": backoff_seconds},
            )
            return "pending"

        await conn.execute(
            text(
                """
                UPDATE jobs
                SET status = 'failed', attempt = :attempt, last_error = :error,
                    lease_owner = NULL, lease_expires_at = NULL, updated_at = now()
                WHERE id = :id
                """
            ),
            {"id": job_id, "attempt": new_attempt, "error": error},
        )
        return "failed"

    async def cancel(self, conn: AsyncConnection, job_id: int) -> None:
        await conn.execute(
            text("UPDATE jobs SET status = 'cancelled', updated_at = now() WHERE id = :id"),
            {"id": job_id},
        )

    async def get(self, conn: AsyncConnection, job_id: int) -> Job | None:
        row = (
            await conn.execute(text(f"SELECT {_JOB_COLUMNS} FROM jobs WHERE id = :id"), {"id": job_id})
        ).mappings().first()
        return _row_to_job(row) if row is not None else None
