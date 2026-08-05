"""Transactional outbox (FR-JOB-07): `enqueue` writes in the caller's own
transaction, so the row exists if and only if the effect it describes was
actually committed. The publisher delivers at-least-once and is safe to
re-run — it only ever moves a row from `pending` to `published`, never the
reverse, and a row already `published` is excluded from the next run."""

from __future__ import annotations

import json
import logging
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

logger = logging.getLogger("uniwatch.platform.outbox")


@dataclass(frozen=True)
class OutboxEvent:
    id: int
    aggregate_type: str
    aggregate_id: str
    event_type: str
    payload: dict
    correlation_id: str


async def enqueue(
    conn: AsyncConnection,
    *,
    aggregate_type: str,
    aggregate_id: str,
    event_type: str,
    payload: dict,
    correlation_id: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO outbox
                    (aggregate_type, aggregate_id, event_type, payload, correlation_id)
                VALUES (:aggregate_type, :aggregate_id, :event_type, CAST(:payload AS jsonb),
                        :correlation_id)
                RETURNING id
                """
            ),
            {
                "aggregate_type": aggregate_type,
                "aggregate_id": aggregate_id,
                "event_type": event_type,
                "payload": json.dumps(payload),
                "correlation_id": correlation_id,
            },
        )
    ).scalar_one()


DeliverCallback = Callable[[OutboxEvent], Awaitable[None]]


class OutboxDeliveryFailed(Exception):
    """Names the event whose delivery failed, so the caller sees which row
    is blocking the queue head instead of only the consumer's own error
    (which carries no outbox context). The batch's transaction rolls back
    with it, so no event is marked `published` on a failed run — the events
    delivered before this one are redelivered on the next run, which
    at-least-once delivery already requires consumers to tolerate."""

    def __init__(self, event: OutboxEvent, delivered_before_failure: int):
        super().__init__(
            f"delivery failed for outbox event {event.id} ({event.event_type} on "
            f"{event.aggregate_type}/{event.aggregate_id}) after {delivered_before_failure} "
            "event(s) delivered in this batch"
        )
        self.event = event
        self.delivered_before_failure = delivered_before_failure


class Publisher:
    def __init__(self, deliver: DeliverCallback):
        """`deliver` performs the actual side effect (webhook, notification,
        ...) and must itself be safe to run more than once for the same
        event — at-least-once delivery means the consumer, not the outbox,
        is responsible for idempotency."""
        self._deliver = deliver

    async def publish_pending(self, conn: AsyncConnection, limit: int = 100) -> list[OutboxEvent]:
        rows = (
            (
                await conn.execute(
                    text(
                        """
                    SELECT id, aggregate_type, aggregate_id, event_type, payload, correlation_id
                    FROM outbox
                    WHERE status = 'pending'
                    ORDER BY created_at ASC
                    LIMIT :limit
                    FOR UPDATE SKIP LOCKED
                    """
                    ),
                    {"limit": limit},
                )
            )
            .mappings()
            .all()
        )

        published: list[OutboxEvent] = []
        for row in rows:
            payload = row["payload"]
            if isinstance(payload, str):
                payload = json.loads(payload)
            event = OutboxEvent(
                id=row["id"],
                aggregate_type=row["aggregate_type"],
                aggregate_id=row["aggregate_id"],
                event_type=row["event_type"],
                payload=payload,
                correlation_id=row["correlation_id"],
            )
            try:
                await self._deliver(event)
            except Exception as exc:
                logger.exception("outbox delivery failed for event %s (%s)", event.id, event.event_type)
                raise OutboxDeliveryFailed(event, len(published)) from exc
            await conn.execute(
                text("UPDATE outbox SET status = 'published', published_at = now() WHERE id = :id"),
                {"id": event.id},
            )
            published.append(event)
        return published
