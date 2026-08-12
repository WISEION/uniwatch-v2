"""Persistence for forecast-card snapshots and human-confirmed tender links
(Phase 4, task 4.D, TENDER_INTELLIGENCE_SPEC.md Section5.4/P310,
Section7.4/P319). forecast_card.py's ForecastCard is otherwise assembled on
demand and discarded -- retaining it is what the >=30-tender P310 backtest
(itself blocked on TBD-TIS-02) needs and has never had.

forecast_card_snapshots / forecast_card_tender_links are append-only
(ADR-0003 layers 3/4) -- no UPDATE/DELETE against either from this module.

observed_lag_days computes a MEASURED DURATION, not a horizon, TTL, or
weight: (tenders.created_at - earliest evidence_chain observed_at).days.
Nothing consumes this value to adjust anything -- accumulating the
measurement is exactly what TBD-TIS-01/TBD-TIS-02 are blocked on.
tenders.created_at is when we first INGESTED the tender, not a real
publication date (no captured eTender field supplies one) -- every response
naming this quantity calls it `first_observed_at`, never "publication
date" (see apps/api_tender/routers/calibration.py)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .forecast_card import ForecastCard


def _observed_at_str(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, datetime):
        return value.isoformat()
    return str(value)


def earliest_observed_at(evidence_chain: list[dict[str, Any]]) -> str | None:
    """Hard ban #3: an evidence chain with no parseable `observed_at` yields
    None, never a guessed/zero duration."""
    parsed = []
    for entry in evidence_chain:
        raw = entry.get("observed_at")
        if raw is None:
            continue
        try:
            parsed.append(datetime.fromisoformat(raw))
        except ValueError:
            continue
    if not parsed:
        return None
    return min(parsed).isoformat()


async def store_forecast_card_snapshot(conn: AsyncConnection, card: ForecastCard, *, computed_at: str) -> int:
    evidence_chain = [{**entry, "observed_at": _observed_at_str(entry.get("observed_at"))} for entry in card.evidence_chain]
    return (
        await conn.execute(
            text(
                """
                INSERT INTO forecast_card_snapshots
                    (object_region, is_composite, signal_types, budget_estimate, evidence_chain, computed_at)
                VALUES (:object_region, :is_composite, CAST(:signal_types AS jsonb), CAST(:budget_estimate AS jsonb),
                        CAST(:evidence_chain AS jsonb), :computed_at)
                RETURNING id
                """
            ),
            {
                "object_region": card.object_region,
                "is_composite": card.is_composite,
                # signal_types is a frozenset on the dataclass -- serialized
                # as a sorted list so the stored JSON is deterministic.
                "signal_types": json.dumps(sorted(card.signal_types)),
                "budget_estimate": json.dumps(card.budget_estimate) if card.budget_estimate is not None else None,
                "evidence_chain": json.dumps(evidence_chain),
                "computed_at": datetime.fromisoformat(computed_at),
            },
        )
    ).scalar_one()


async def load_forecast_card_snapshot(conn: AsyncConnection, *, snapshot_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, object_region, is_composite, signal_types, budget_estimate, evidence_chain, computed_at
                    FROM forecast_card_snapshots WHERE id = :snapshot_id
                    """
                ),
                {"snapshot_id": snapshot_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    row_dict = dict(row)
    if isinstance(row_dict["signal_types"], str):
        row_dict["signal_types"] = json.loads(row_dict["signal_types"])
    if isinstance(row_dict["budget_estimate"], str):
        row_dict["budget_estimate"] = json.loads(row_dict["budget_estimate"])
    if isinstance(row_dict["evidence_chain"], str):
        row_dict["evidence_chain"] = json.loads(row_dict["evidence_chain"])
    return row_dict


async def confirm_forecast_tender_link(
    conn: AsyncConnection, *, snapshot_id: int, tender_id: int, note: str, confirmed_by: str, confirmed_at: str
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO forecast_card_tender_links
                    (forecast_card_snapshot_id, tender_id, note, confirmed_by, confirmed_at)
                VALUES (:snapshot_id, :tender_id, :note, :confirmed_by, :confirmed_at)
                RETURNING id
                """
            ),
            {
                "snapshot_id": snapshot_id,
                "tender_id": tender_id,
                "note": note,
                "confirmed_by": confirmed_by,
                "confirmed_at": datetime.fromisoformat(confirmed_at),
            },
        )
    ).scalar_one()


async def list_links_by_snapshot(conn: AsyncConnection, *, snapshot_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, forecast_card_snapshot_id, tender_id, note, confirmed_by, confirmed_at
                    FROM forecast_card_tender_links WHERE forecast_card_snapshot_id = :snapshot_id ORDER BY id
                    """
                ),
                {"snapshot_id": snapshot_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def observed_lag_days(conn: AsyncConnection, *, snapshot_id: int, tender_id: int) -> int | None:
    snapshot = await load_forecast_card_snapshot(conn, snapshot_id=snapshot_id)
    if snapshot is None:
        return None
    first_observed_at = earliest_observed_at(snapshot["evidence_chain"])
    if first_observed_at is None:
        return None

    created_at = (
        await conn.execute(text("SELECT created_at FROM tenders WHERE id = :tender_id"), {"tender_id": tender_id})
    ).scalar_one()
    return (created_at - datetime.fromisoformat(first_observed_at)).days
