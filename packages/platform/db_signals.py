"""DB connections/locks/storage signal (Phase 6, task 6.C, master plan
§23.1's "DB connections/locks/storage" line). Direct SQL against Postgres's
own catalog views -- pg_stat_activity/pg_locks/pg_database_size -- since no
domain table tracks this; this is the one signal category this module owns
because it has no natural home in any domain package."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def connection_and_storage_signals(conn: AsyncConnection) -> dict[str, Any]:
    active_connections = (
        await conn.execute(text("SELECT count(*) FROM pg_stat_activity WHERE datname = current_database()"))
    ).scalar_one()
    waiting_locks = (await conn.execute(text("SELECT count(*) FROM pg_locks WHERE NOT granted"))).scalar_one()
    database_size_bytes = (await conn.execute(text("SELECT pg_database_size(current_database())"))).scalar_one()
    return {
        "active_connections": active_connections,
        "waiting_locks": waiting_locks,
        "database_size_bytes": database_size_bytes,
    }
