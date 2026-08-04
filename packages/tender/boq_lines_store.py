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

from .boq_line_model import BoqLine


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
