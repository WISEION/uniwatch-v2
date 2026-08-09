"""Post-submission tracking (Task 4.B, TENDER_INTELLIGENCE_SPEC.md §7.2,
P317): re-checks one already-decided (bid/conditional_bid) tender's
event_details on eTender, and -- only if something changed -- re-walks its
BOM-lines pages to find which specific lines changed. The event_details
re-check reuses the EXISTING immutable versioning (ingest_event_details
already creates a new tender_versions row per call, never an overwrite).
The BOM-lines re-walk is diffed IN MEMORY ONLY against the already-stored
boq_lines rows -- it never calls store_boq_lines again for this event_id,
because boq_lines has no schema support for a second generation of the same
source_line_id (UNIQUE (source, event_id, source_line_id), no upsert)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception

from .boq_line_diff import diff_boq_lines
from .boq_line_model import build_boq_lines
from .boq_lines_store import list_boq_lines_by_event
from .change_tracking_store import store_boq_line_recalc_flag, store_tender_change_event, upsert_watch_state
from .etender_connector import ingest_event_details
from .normalized import get_current_tender_version_id, get_event_id_for_tender
from .schema_drift import SchemaDriftDetected
from .tender_change_detection import classify_change_type, diff_normalized_fields

JOB_TYPE = "tender_change_check"

FetchEventDetails = Callable[[int], Awaitable[tuple[bytes, dict[str, Any]]]]
FetchBomPage = Callable[[int, int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def check_tender_for_changes(
    conn: AsyncConnection,
    *,
    tender_id: int,
    fetch_event_details: FetchEventDetails,
    fetch_bom_page: FetchBomPage,
    correlation_id: str,
    observed_at: str,
) -> dict[str, Any]:
    event_id = await get_event_id_for_tender(conn, tender_id=tender_id)
    if event_id is None:
        raise ValueError(f"tender {tender_id} has no resolvable event id -- cannot track for changes")

    previous_version_id = await get_current_tender_version_id(conn, tender_id=tender_id)
    previous_fields: dict[str, Any] = {}
    if previous_version_id is not None:
        row = (
            await conn.execute(
                text("SELECT normalized_fields FROM tender_versions WHERE id = :id"),
                {"id": previous_version_id},
            )
        ).first()
        if row is not None:
            value = row[0]
            previous_fields = json.loads(value) if isinstance(value, str) else value

    raw_body, payload = await fetch_event_details(event_id)

    try:
        new_version = await ingest_event_details(conn, raw_body=raw_body, payload=payload, correlation_id=correlation_id)
    except SchemaDriftDetected as drift_exc:
        await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason=str(drift_exc),
            correlation_id=correlation_id,
            raw_ref=drift_exc.raw_snapshot_id,
            contract_name=drift_exc.contract_name,
        )
        await upsert_watch_state(conn, tender_id=tender_id, checked_at=observed_at)
        return {"change_detected": False, "change_type": None, "flagged_line_count": 0}

    changes = diff_normalized_fields(previous_fields, new_version.normalized_fields)
    flagged_line_count = 0
    change_type: str | None = None

    if changes:
        change_type = classify_change_type(changes)
        change_event_id = await store_tender_change_event(
            conn,
            tender_id=tender_id,
            change_type=change_type,
            changed_fields=changes,
            detected_at=observed_at,
            raw_snapshot_id=new_version.raw_snapshot_id,
        )

        old_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id)
        new_lines = []
        page_number = 1
        while True:
            _page_raw_body, page_payload = await fetch_bom_page(event_id, page_number)
            new_lines.extend(build_boq_lines(page_number=page_number, items=page_payload["items"]))
            total_pages = page_payload.get("totalPages")
            if total_pages is None or page_number >= total_pages:
                break
            page_number += 1

        changed_line_ids = diff_boq_lines(old_lines, new_lines)
        for source_line_id in changed_line_ids:
            await store_boq_line_recalc_flag(
                conn,
                tender_id=tender_id,
                boqline_source_line_id=source_line_id,
                change_event_id=change_event_id,
                flagged_at=observed_at,
            )
        flagged_line_count = len(changed_line_ids)

    await upsert_watch_state(conn, tender_id=tender_id, checked_at=observed_at)

    return {"change_detected": bool(changes), "change_type": change_type, "flagged_line_count": flagged_line_count}
