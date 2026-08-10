"""Persistence for Execution Ledger facts (Phase 4, task 4.C,
TENDER_INTELLIGENCE_SPEC.md Section7.3, P318). execution_facts is append-only
(ADR-0003 layer 2/3) -- no UPDATE/DELETE against it from this module."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .execution_fact_model import ExecutionFact


async def store_execution_fact(conn: AsyncConnection, fact: ExecutionFact) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO execution_facts
                    (tender_id, boqline_source_line_id, planned_qty, actual_qty, deviation_reason,
                     deviation_category, culprit_type, culprit_vendor_name, culprit_vendor_id,
                     evidence_source, observed_at)
                VALUES
                    (:tender_id, :boqline_source_line_id, :planned_qty, :actual_qty, :deviation_reason,
                     :deviation_category, :culprit_type, :culprit_vendor_name, :culprit_vendor_id,
                     :evidence_source, :observed_at)
                RETURNING id
                """
            ),
            {
                "tender_id": fact.tender_id,
                "boqline_source_line_id": fact.boqline_source_line_id,
                "planned_qty": fact.planned_qty,
                "actual_qty": fact.actual_qty,
                "deviation_reason": fact.deviation_reason,
                "deviation_category": fact.deviation_category,
                "culprit_type": fact.culprit_type,
                "culprit_vendor_name": fact.culprit_vendor_name,
                "culprit_vendor_id": fact.culprit_vendor_id,
                "evidence_source": fact.evidence_source,
                # asyncpg binds TIMESTAMPTZ params by native datetime, not
                # by ISO string -- same discipline as signals_store.py /
                # vendor_store.py / reputation_store.py / decision_store.py.
                "observed_at": datetime.fromisoformat(fact.observed_at),
            },
        )
    ).scalar_one()


async def list_execution_facts_by_tender(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, boqline_source_line_id, planned_qty, actual_qty, deviation_reason,
                           deviation_category, culprit_type, culprit_vendor_name, culprit_vendor_id,
                           evidence_source, observed_at
                    FROM execution_facts WHERE tender_id = :tender_id ORDER BY id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
