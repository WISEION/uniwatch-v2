"""FR-JOB-07: transactional outbox, at-least-once delivery, idempotent-safe
publisher re-run."""

from __future__ import annotations

import pytest
from sqlalchemy import text

from packages.platform.outbox import OutboxDeliveryFailed, Publisher, enqueue


async def test_outbox_row_committed_together_with_caller_effect(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('r1') RETURNING id"))).scalar()
        await enqueue(
            conn,
            aggregate_type="role",
            aggregate_id=str(role_id),
            event_type="role.created",
            payload={"name": "r1"},
            correlation_id="corr-outbox-1",
        )

    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT event_type, correlation_id, status FROM outbox WHERE aggregate_id = :id"),
                    {"id": str(role_id)},
                )
            )
            .mappings()
            .first()
        )
    assert row["event_type"] == "role.created"
    assert row["correlation_id"] == "corr-outbox-1"
    assert row["status"] == "pending"


async def test_rolled_back_transaction_leaves_no_outbox_row(engine):
    role_id = 424242
    try:
        async with engine.begin() as conn:
            await enqueue(
                conn,
                aggregate_type="role",
                aggregate_id=str(role_id),
                event_type="role.created",
                payload={"name": "will-not-exist"},
                correlation_id="corr-outbox-rollback",
            )
            raise RuntimeError("simulated failure before commit")
    except RuntimeError:
        pass

    async with engine.begin() as conn:
        row = (await conn.execute(text("SELECT id FROM outbox WHERE aggregate_id = :id"), {"id": str(role_id)})).first()
    assert row is None


async def test_publisher_delivers_each_pending_event_once(engine):
    delivered = []

    async def deliver(event):
        delivered.append(event)

    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('r2') RETURNING id"))).scalar()
        await enqueue(
            conn,
            aggregate_type="role",
            aggregate_id=str(role_id),
            event_type="role.created",
            payload={"name": "r2"},
            correlation_id="corr-outbox-2",
        )

    publisher = Publisher(deliver)
    async with engine.begin() as conn:
        published = await publisher.publish_pending(conn)
    assert len(published) == 1
    assert len(delivered) == 1
    assert delivered[0].event_type == "role.created"


async def test_failed_delivery_surfaces_which_event_blocked_and_publishes_nothing(engine):
    """A consumer error must not be swallowed into a shorter `published`
    list that looks like an empty queue: it propagates, named with the event
    it happened on, and the batch's transaction leaves every row `pending`."""

    async def deliver(event):
        raise RuntimeError("webhook endpoint refused the connection")

    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('r4') RETURNING id"))).scalar()
        event_id = await enqueue(
            conn,
            aggregate_type="role",
            aggregate_id=str(role_id),
            event_type="role.created",
            payload={"name": "r4"},
            correlation_id="corr-outbox-4",
        )

    publisher = Publisher(deliver)
    with pytest.raises(OutboxDeliveryFailed) as exc_info:
        async with engine.begin() as conn:
            await publisher.publish_pending(conn)
    assert exc_info.value.event.id == event_id
    assert isinstance(exc_info.value.__cause__, RuntimeError)

    async with engine.begin() as conn:
        status = (await conn.execute(text("SELECT status FROM outbox WHERE id = :id"), {"id": event_id})).scalar()
    assert status == "pending"


async def test_publisher_rerun_is_idempotent_no_op_for_already_published(engine):
    delivered = []

    async def deliver(event):
        delivered.append(event)

    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('r3') RETURNING id"))).scalar()
        await enqueue(
            conn,
            aggregate_type="role",
            aggregate_id=str(role_id),
            event_type="role.created",
            payload={"name": "r3"},
            correlation_id="corr-outbox-3",
        )

    publisher = Publisher(deliver)
    async with engine.begin() as conn:
        await publisher.publish_pending(conn)
    async with engine.begin() as conn:
        second_run = await publisher.publish_pending(conn)

    assert second_run == []
    assert len(delivered) == 1  # not delivered a second time
