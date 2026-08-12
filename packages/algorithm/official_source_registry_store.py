"""Persistence for the official-source registry (Phase 5, task 5.A).
Append-only: no update/delete function -- a superseded rate is a new row
with its own effective_from, never an edit of the old row (same discipline
as overhead_buffer_contributions)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .official_source_registry_model import OfficialSource


async def store_official_source(conn: AsyncConnection, source: OfficialSource) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO official_sources
                    (source_type, name, citation, value, effective_from, effective_to, entered_by, entered_at)
                VALUES
                    (:source_type, :name, :citation, :value, :effective_from, :effective_to, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "source_type": source.source_type,
                "name": source.name,
                "citation": source.citation,
                "value": source.value,
                "effective_from": datetime.fromisoformat(source.effective_from),
                "effective_to": datetime.fromisoformat(source.effective_to) if source.effective_to else None,
                "entered_by": source.entered_by,
                "entered_at": datetime.fromisoformat(source.entered_at),
            },
        )
    ).scalar_one()


async def get_effective_source(conn: AsyncConnection, *, source_type: str, name: str, as_of: str) -> dict[str, Any] | None:
    """Latest row for (source_type, name) whose effective window covers
    as_of -- effective_to NULL means still in effect."""
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, source_type, name, citation, value, effective_from, effective_to, entered_by, entered_at
                    FROM official_sources
                    WHERE source_type = :source_type AND name = :name
                      AND effective_from <= :as_of
                      AND (effective_to IS NULL OR effective_to > :as_of)
                    ORDER BY effective_from DESC
                    LIMIT 1
                    """
                ),
                {"source_type": source_type, "name": name, "as_of": datetime.fromisoformat(as_of)},
            )
        )
        .mappings()
        .first()
    )
    return None if row is None else dict(row)


async def list_sources_by_type(conn: AsyncConnection, *, source_type: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, source_type, name, citation, value, effective_from, effective_to, entered_by, entered_at
                    FROM official_sources WHERE source_type = :source_type ORDER BY name, effective_from
                    """
                ),
                {"source_type": source_type},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
