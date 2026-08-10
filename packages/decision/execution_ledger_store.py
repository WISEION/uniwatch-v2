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


async def store_overhead_buffer_contribution(
    conn: AsyncConnection, *, tender_id: int, deviation_category: str, fact_count: int, contributed_at: str
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO overhead_buffer_contributions (tender_id, deviation_category, fact_count, contributed_at)
                VALUES (:tender_id, :deviation_category, :fact_count, :contributed_at)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "deviation_category": deviation_category,
                "fact_count": fact_count,
                # asyncpg binds TIMESTAMPTZ params by native datetime, not
                # by ISO string -- same discipline as store_execution_fact
                # above.
                "contributed_at": datetime.fromisoformat(contributed_at),
            },
        )
    ).scalar_one()


async def list_execution_facts_by_organization_voen(conn: AsyncConnection, *, organization_voen: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT ef.id, ef.tender_id, ef.boqline_source_line_id, ef.planned_qty, ef.actual_qty,
                           ef.deviation_reason, ef.deviation_category, ef.culprit_type, ef.observed_at
                    FROM execution_facts ef
                    WHERE ef.culprit_type = 'customer'
                      AND ef.tender_id IN (
                        SELECT tender_id FROM (
                            SELECT DISTINCT ON (tender_id) tender_id, normalized_fields
                            FROM tender_versions
                            ORDER BY tender_id, id DESC
                        ) latest
                        WHERE latest.normalized_fields ->> 'organization_voen' = :organization_voen
                      )
                    ORDER BY ef.tender_id, ef.id
                    """
                ),
                {"organization_voen": organization_voen},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
