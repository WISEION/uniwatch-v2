"""Reputation-fact persistence (task 3.B, TENDER_INTELLIGENCE_SPEC.md
Section6.2). Same explicit-realm discipline as vendor_store.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .reputation_model import ReputationFact


async def store_reputation_fact(conn: AsyncConnection, vendor_id: int, fact: ReputationFact) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendor_reputation_facts
                    (vendor_id, data_realm, watermark, event_type, project_ref, source_ref, observed_at, ttl_days)
                VALUES (:vendor_id, :data_realm, :watermark, :event_type, :project_ref, :source_ref,
                        :observed_at, :ttl_days)
                RETURNING id
                """
            ),
            {
                "vendor_id": vendor_id,
                "data_realm": fact.data_realm,
                "watermark": fact.watermark,
                "event_type": fact.event_type,
                "project_ref": fact.project_ref,
                "source_ref": fact.source_ref,
                "observed_at": datetime.fromisoformat(fact.observed_at),
                "ttl_days": fact.ttl_days,
            },
        )
    ).scalar_one()


async def list_active_reputation_facts(conn: AsyncConnection, *, vendor_id: int, as_of: str) -> list[dict[str, Any]]:
    """Facts whose TTL (observed_at + ttl_days) has not yet expired as of
    `as_of` -- an expired fact is excluded, never silently included past
    its TTL."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, vendor_id, data_realm, watermark, event_type, project_ref, source_ref,
                           observed_at, ttl_days
                    FROM vendor_reputation_facts
                    WHERE vendor_id = :vendor_id
                      AND observed_at + (ttl_days * interval '1 day') > :as_of
                    ORDER BY id
                    """
                ),
                {"vendor_id": vendor_id, "as_of": datetime.fromisoformat(as_of)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
