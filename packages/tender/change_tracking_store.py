"""Persistence for Task 4.B's post-submission tracking (Phase 4,
TENDER_INTELLIGENCE_SPEC.md §7.2, P317). tender_change_events and
boq_line_recalc_flags are append-only -- no UPDATE/DELETE against either
from this module. tender_watch_state is the one mutable table (an
operational high-water-mark, not a fact or a human decision)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .tender_change_detection import TenderFieldChange


async def store_tender_change_event(
    conn: AsyncConnection,
    *,
    tender_id: int,
    change_type: str,
    changed_fields: tuple[TenderFieldChange, ...],
    detected_at: str,
    raw_snapshot_id: int,
) -> int:
    changed_fields_json = json.dumps(
        [{"field": c.field, "old_value": c.old_value, "new_value": c.new_value} for c in changed_fields]
    )
    return (
        await conn.execute(
            text(
                """
                INSERT INTO tender_change_events
                    (tender_id, change_type, changed_fields, detected_at, raw_snapshot_id)
                VALUES (:tender_id, :change_type, CAST(:changed_fields AS jsonb), :detected_at, :raw_snapshot_id)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "change_type": change_type,
                "changed_fields": changed_fields_json,
                "detected_at": datetime.fromisoformat(detected_at),
                "raw_snapshot_id": raw_snapshot_id,
            },
        )
    ).scalar_one()


async def store_boq_line_recalc_flag(
    conn: AsyncConnection,
    *,
    tender_id: int,
    boqline_source_line_id: int,
    change_event_id: int,
    flagged_at: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO boq_line_recalc_flags
                    (tender_id, boqline_source_line_id, change_event_id, flagged_at)
                VALUES (:tender_id, :boqline_source_line_id, :change_event_id, :flagged_at)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "boqline_source_line_id": boqline_source_line_id,
                "change_event_id": change_event_id,
                "flagged_at": datetime.fromisoformat(flagged_at),
            },
        )
    ).scalar_one()


async def list_unresolved_recalc_flags(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, boqline_source_line_id, change_event_id, flagged_at
                    FROM boq_line_recalc_flags
                    WHERE tender_id = :tender_id AND resolved_at IS NULL
                    ORDER BY flagged_at, id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def get_watch_state(conn: AsyncConnection, *, tender_id: int) -> str | None:
    row = (
        await conn.execute(
            text("SELECT last_checked_at FROM tender_watch_state WHERE tender_id = :tender_id"), {"tender_id": tender_id}
        )
    ).first()
    if row is None:
        return None
    return row[0].isoformat()


async def upsert_watch_state(conn: AsyncConnection, *, tender_id: int, checked_at: str) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO tender_watch_state (tender_id, last_checked_at)
            VALUES (:tender_id, :checked_at)
            ON CONFLICT (tender_id) DO UPDATE SET last_checked_at = EXCLUDED.last_checked_at
            """
        ),
        {"tender_id": tender_id, "checked_at": datetime.fromisoformat(checked_at)},
    )


async def list_tenders_due_for_check(conn: AsyncConnection, *, tender_ids: list[int], now: str, interval_hours: int) -> list[int]:
    if not tender_ids:
        return []
    rows = (
        await conn.execute(
            text(
                """
                SELECT t.id AS tender_id
                FROM unnest(CAST(:tender_ids AS bigint[])) AS t(id)
                LEFT JOIN tender_watch_state w ON w.tender_id = t.id
                WHERE w.last_checked_at IS NULL
                   OR w.last_checked_at <= CAST(:now AS timestamptz) - make_interval(hours => :interval_hours)
                ORDER BY t.id
                """
            ),
            {"tender_ids": tender_ids, "now": datetime.fromisoformat(now), "interval_hours": interval_hours},
        )
    ).all()
    return [row[0] for row in rows]
