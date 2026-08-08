"""BOQ line persistence (FR-TND-*, P308). One INSERT per BoqLine, in the
caller's own transaction -- no ON CONFLICT/upsert here: `boq_lines`' unique
constraint on (source, event_id, source_line_id) is a real invariant guard,
and a violation should surface as a genuine error rather than being
silently absorbed (the job-loop transaction wrapping this already
guarantees a page's lines are only durably stored if the whole page's
processing commits, so a legitimate duplicate insert should not happen in
normal operation)."""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .boq_line_model import BoqLine, SpecRequirement


async def store_boq_lines(
    conn: AsyncConnection,
    *,
    source: str,
    event_id: int,
    tender_version_id: int,
    raw_snapshot_id: int,
    lines: list[BoqLine],
) -> int:
    for line in lines:
        await conn.execute(
            text(
                """
                INSERT INTO boq_lines
                    (source, event_id, page_number, tender_version_id, raw_snapshot_id, source_line_id,
                     section, category_code, description, unit_raw, unit_canonical, unit_status, qty,
                     line_type, spec_requirements, rate, amount)
                VALUES
                    (:source, :event_id, :page_number, :tender_version_id, :raw_snapshot_id, :source_line_id,
                     :section, :category_code, :description, :unit_raw, :unit_canonical, :unit_status, :qty,
                     :line_type, CAST(:spec_requirements AS jsonb), :rate, :amount)
                """
            ),
            {
                "source": source,
                "event_id": event_id,
                "page_number": line.page_number,
                "tender_version_id": tender_version_id,
                "raw_snapshot_id": raw_snapshot_id,
                "source_line_id": line.source_line_id,
                "section": line.section,
                "category_code": line.category_code,
                "description": line.description,
                "unit_raw": line.unit_raw,
                "unit_canonical": line.unit_canonical,
                "unit_status": line.unit_status,
                "qty": line.qty,
                "line_type": line.line_type,
                "spec_requirements": json.dumps([{"kind": r.kind, "raw_text": r.raw_text} for r in line.spec_requirements]),
                "rate": line.rate,
                "amount": line.amount,
            },
        )
    return len(lines)


async def list_boq_lines_by_event(conn: AsyncConnection, *, source: str, event_id: int) -> list[BoqLine]:
    """Queries the real BOQ aggregate key (source, event_id) --
    boq_lines_event_idx -- rather than a single tender_version_id: a real
    tender's BOQ is ingested one page at a time, each page landing under its
    own tender_version (see etender_connector.py's ingest_bom_lines_page,
    whose identity_query_keys include PageNumber), so no single
    tender_version_id holds a whole tender's lines (Task 4.A Final Review,
    finding C1). Callers resolve event_id via
    packages/tender/normalized.py's get_event_id_for_tender."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT page_number, source_line_id, section, category_code, description, unit_raw,
                           unit_canonical, unit_status, qty, line_type, spec_requirements, rate, amount
                    FROM boq_lines WHERE source = :source AND event_id = :event_id
                    ORDER BY page_number, source_line_id
                    """
                ),
                {"source": source, "event_id": event_id},
            )
        )
        .mappings()
        .all()
    )
    lines: list[BoqLine] = []
    for row in rows:
        raw_specs = row["spec_requirements"]
        if isinstance(raw_specs, str):
            raw_specs = json.loads(raw_specs)
        lines.append(
            BoqLine(
                source_line_id=row["source_line_id"],
                page_number=row["page_number"],
                section=row["section"],
                category_code=row["category_code"],
                description=row["description"],
                unit_raw=row["unit_raw"],
                unit_canonical=row["unit_canonical"],
                unit_status=row["unit_status"],
                qty=row["qty"],
                line_type=row["line_type"],
                spec_requirements=tuple(SpecRequirement(kind=s["kind"], raw_text=s["raw_text"]) for s in raw_specs),
                rate=row["rate"],
                amount=row["amount"],
            )
        )
    return lines
