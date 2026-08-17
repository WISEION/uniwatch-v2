"""BOQ completeness contract (FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04, P001).

A BOQ import is `complete` only after every expected page has been fetched
AND the summed stored line count matches the source's own claimed total
(`totalItems`). Absence of a source-provided total is
`source_exhausted_unverified`, never `complete` -- there is no ground truth
to reconcile against in that case. If fetching stops (job terminally
failed or cancelled) before reaching `complete` while a total *is* known,
the record becomes `incomplete` with the exact missing page numbers listed
-- never silently reported as done.
"""

from __future__ import annotations

import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class BoqImportStatus:
    id: int
    source: str
    event_id: int
    expected_total: int | None
    expected_pages: int | None
    fetched_pages: int
    stored_lines: int
    status: str
    missing_pages: list[int]
    page_checksums: dict[str, str]


def _row_to_status(row) -> BoqImportStatus:
    missing_pages = row["missing_pages"]
    if isinstance(missing_pages, str):
        missing_pages = json.loads(missing_pages)
    page_checksums = row["page_checksums"]
    if isinstance(page_checksums, str):
        page_checksums = json.loads(page_checksums)
    return BoqImportStatus(
        id=row["id"],
        source=row["source"],
        event_id=row["event_id"],
        expected_total=row["expected_total"],
        expected_pages=row["expected_pages"],
        fetched_pages=row["fetched_pages"],
        stored_lines=row["stored_lines"],
        status=row["status"],
        missing_pages=missing_pages,
        page_checksums=page_checksums,
    )


_COLUMNS = """id, source, event_id, expected_total, expected_pages, fetched_pages,
              stored_lines, status, missing_pages, page_checksums"""


async def get_or_create_boq_import(conn: AsyncConnection, *, source: str, event_id: int) -> BoqImportStatus:
    existing = (
        (
            await conn.execute(
                text(f"SELECT {_COLUMNS} FROM boq_import WHERE source = :source AND event_id = :event_id"),
                {"source": source, "event_id": event_id},
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return _row_to_status(existing)

    row = (
        (
            await conn.execute(
                text(f"INSERT INTO boq_import (source, event_id) VALUES (:source, :event_id) RETURNING {_COLUMNS}"),
                {"source": source, "event_id": event_id},
            )
        )
        .mappings()
        .one()
    )
    return _row_to_status(row)


async def record_page_fetched(
    conn: AsyncConnection,
    *,
    source: str,
    event_id: int,
    page_number: int,
    lines_on_page: int,
    expected_total: int | None,
    expected_pages: int | None,
    page_checksum: str,
) -> BoqImportStatus:
    """Called once per page, AFTER that page's raw snapshot and normalized
    version have already been committed in the same DB transaction -- this
    only updates reconciliation counters, it never itself decides whether
    the page's content is durable."""
    current = await get_or_create_boq_import(conn, source=source, event_id=event_id)

    fetched_pages = current.fetched_pages + 1
    stored_lines = current.stored_lines + lines_on_page
    page_checksums = {**current.page_checksums, str(page_number): page_checksum}

    if expected_total is None or expected_pages is None:
        status = "source_exhausted_unverified"
    elif fetched_pages == expected_pages and stored_lines == expected_total:
        status = "complete"
    else:
        status = "in_progress"

    row = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE boq_import
                    SET expected_total = :expected_total,
                        expected_pages = :expected_pages,
                        fetched_pages = :fetched_pages,
                        stored_lines = :stored_lines,
                        status = :status,
                        page_checksums = CAST(:page_checksums AS jsonb),
                        updated_at = now()
                    WHERE id = :id
                    RETURNING {_COLUMNS}
                    """
                ),
                {
                    "id": current.id,
                    "expected_total": expected_total,
                    "expected_pages": expected_pages,
                    "fetched_pages": fetched_pages,
                    "stored_lines": stored_lines,
                    "status": status,
                    "page_checksums": json.dumps(page_checksums),
                },
            )
        )
        .mappings()
        .one()
    )
    return _row_to_status(row)


async def count_by_status(conn: AsyncConnection) -> dict[str, int]:
    """BOQ completeness signal (master plan §23.1): count of boq_import rows
    per status -- 'complete' / 'incomplete' / 'in_progress' /
    'source_exhausted_unverified' (INV-04's own status set, see hard ban
    #5 -- never invented, never collapsed into a binary complete/not)."""
    rows = (await conn.execute(text("SELECT status, count(*) AS n FROM boq_import GROUP BY status"))).all()
    return {row.status: row.n for row in rows}


async def mark_import_stalled(conn: AsyncConnection, *, source: str, event_id: int) -> BoqImportStatus:
    """Called when the fetching job stops trying (terminal failure or
    cancel) before completeness was proven. If a total was known, the
    exact missing page numbers are recorded and status becomes
    `incomplete` -- never silently left looking like it might still be
    fine. If no total was ever known, this is a no-op on status (it stays
    `source_exhausted_unverified`, which already says as much as can be
    said)."""
    current = await get_or_create_boq_import(conn, source=source, event_id=event_id)

    if current.status in ("complete", "source_exhausted_unverified"):
        return current

    expected_pages = current.expected_pages
    if expected_pages is None:
        return current

    fetched_page_numbers = {int(p) for p in current.page_checksums}
    missing = sorted(set(range(1, expected_pages + 1)) - fetched_page_numbers)

    row = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE boq_import
                    SET status = 'incomplete', missing_pages = CAST(:missing_pages AS jsonb), updated_at = now()
                    WHERE id = :id
                    RETURNING {_COLUMNS}
                    """
                ),
                {"id": current.id, "missing_pages": json.dumps(missing)},
            )
        )
        .mappings()
        .one()
    )
    return _row_to_status(row)
