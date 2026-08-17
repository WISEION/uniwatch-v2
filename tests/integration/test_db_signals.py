"""DB connections/locks/storage signal (Phase 6, task 6.C, master plan
§23.1)."""

from __future__ import annotations

from packages.platform.db_signals import connection_and_storage_signals


async def test_connection_and_storage_signals_returns_real_values(engine):
    async with engine.connect() as conn:
        signals = await connection_and_storage_signals(conn)

    assert signals["active_connections"] >= 1
    assert signals["waiting_locks"] >= 0
    assert signals["database_size_bytes"] > 0
