"""FR-PLT-03, P111."""

from __future__ import annotations

import pytest

from packages.platform.idempotency import (
    IdempotencyKeyReused,
    IdempotencyReservationMissing,
    IdempotencyStore,
    fingerprint,
)


async def test_new_key_reserves_and_returns_none(engine):
    store = IdempotencyStore()
    async with engine.begin() as conn:
        record = await store.reserve(conn, "key-1", "/things", fingerprint({"a": 1}))
    assert record is None


async def test_replaying_same_key_and_fingerprint_returns_stored_response(engine):
    store = IdempotencyStore()
    fp = fingerprint({"a": 1})
    async with engine.begin() as conn:
        assert await store.reserve(conn, "key-2", "/things", fp) is None
        await store.store_response(conn, "key-2", "/things", 201, {"id": "abc"})

    async with engine.begin() as conn:
        record = await store.reserve(conn, "key-2", "/things", fp)
    assert record is not None
    assert record.response_status == 201
    assert record.response_body == {"id": "abc"}


async def test_reusing_key_for_different_request_raises(engine):
    store = IdempotencyStore()
    async with engine.begin() as conn:
        assert await store.reserve(conn, "key-3", "/things", fingerprint({"deadline": "2026-09-01"})) is None
        await store.store_response(conn, "key-3", "/things", 201, {"id": "x"})

    async with engine.begin() as conn:
        with pytest.raises(IdempotencyKeyReused):
            await store.reserve(conn, "key-3", "/things", fingerprint({"deadline": "2026-09-15"}))


async def test_storing_a_response_without_a_reservation_raises(engine):
    """A zero-row UPDATE would leave the key with no stored response, so the
    next replay would repeat the mutation instead of replaying the result --
    that cannot pass silently."""
    store = IdempotencyStore()
    async with engine.begin() as conn:
        with pytest.raises(IdempotencyReservationMissing):
            await store.store_response(conn, "key-never-reserved", "/things", 201, {"id": "x"})


async def test_same_key_different_route_is_independent(engine):
    store = IdempotencyStore()
    fp = fingerprint({"a": 1})
    async with engine.begin() as conn:
        first = await store.reserve(conn, "key-shared", "/things", fp)
        second = await store.reserve(conn, "key-shared", "/others", fp)
    assert first is None
    assert second is None
