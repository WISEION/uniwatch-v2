"""Persistence for calibration-loop inputs (Phase 4, task 4.D,
TENDER_INTELLIGENCE_SPEC.md Section7.4, P319). tender_outcomes and
tender_loss_reasons are append-only (ADR-0003 layer 4 -- both are human
entries) -- no UPDATE/DELETE against either from this module.

list_overhead_buffer_contributions closes a real gap left by task 4.C:
overhead_buffer_contributions was write-only, with its only read being a
409 existence probe in the close-project route. Nothing had ever SELECTed
fact_count. This function reads the counts as they are -- it applies no
weighting, because no source supplies one (hard ban #2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .calibration_model import LossReason, TenderOutcome


def _ts(value: str | None) -> datetime | None:
    # asyncpg binds TIMESTAMPTZ by native datetime, not ISO string -- same
    # discipline as execution_ledger_store.py.
    return None if value is None else datetime.fromisoformat(value)


async def store_tender_outcome(conn: AsyncConnection, outcome: TenderOutcome) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO tender_outcomes
                    (tender_id, outcome, our_submitted_amount, winner_name, winner_amount,
                     currency, announced_at, source_ref, entered_by, entered_at)
                VALUES
                    (:tender_id, :outcome, :our_submitted_amount, :winner_name, :winner_amount,
                     :currency, :announced_at, :source_ref, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "tender_id": outcome.tender_id,
                "outcome": outcome.outcome,
                "our_submitted_amount": outcome.our_submitted_amount,
                "winner_name": outcome.winner_name,
                "winner_amount": outcome.winner_amount,
                "currency": outcome.currency,
                "announced_at": _ts(outcome.announced_at),
                "source_ref": outcome.source_ref,
                "entered_by": outcome.entered_by,
                "entered_at": _ts(outcome.entered_at),
            },
        )
    ).scalar_one()


async def load_tender_outcome(conn: AsyncConnection, *, tender_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, outcome, our_submitted_amount, winner_name, winner_amount,
                           currency, announced_at, source_ref, entered_by, entered_at
                    FROM tender_outcomes WHERE tender_id = :tender_id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .first()
    )
    return None if row is None else dict(row)


async def store_loss_reason(conn: AsyncConnection, reason: LossReason, *, tender_outcome_id: int) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO tender_loss_reasons
                    (tender_outcome_id, loss_reason, note, entered_by, entered_at)
                VALUES (:tender_outcome_id, :loss_reason, :note, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "tender_outcome_id": tender_outcome_id,
                "loss_reason": reason.loss_reason,
                "note": reason.note,
                "entered_by": reason.entered_by,
                "entered_at": _ts(reason.entered_at),
            },
        )
    ).scalar_one()


async def list_loss_reasons_by_outcome(conn: AsyncConnection, *, tender_outcome_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_outcome_id, loss_reason, note, entered_by, entered_at
                    FROM tender_loss_reasons WHERE tender_outcome_id = :tender_outcome_id ORDER BY id
                    """
                ),
                {"tender_outcome_id": tender_outcome_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def list_overhead_buffer_contributions(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, deviation_category, fact_count, contributed_at
                    FROM overhead_buffer_contributions WHERE tender_id = :tender_id ORDER BY id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
