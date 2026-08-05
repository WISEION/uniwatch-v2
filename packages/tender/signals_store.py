"""Append-only signal-fact storage (INV-15, INV-16, INV-17). A signal is
never UPDATEd -- a re-observation is always a new INSERT, same discipline
as raw_snapshot.py, because a signal IS an observation at a point in time,
not a mutable current-state row."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .forecast_card import ForecastCard, build_forecast_card
from .object_intersection import ObjectIntersection, detect_intersection
from .signal_model import Signal


async def store_signal(conn: AsyncConnection, signal: Signal) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO signals
                    (signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
                     confidence, object_customer, object_region, object_project_type, correlation_id)
                VALUES (:signal_type, :source, :raw_snapshot_id, CAST(:value AS jsonb), :observed_at,
                        :ttl_class, :confidence, :object_customer, :object_region, :object_project_type,
                        :correlation_id)
                RETURNING id
                """
            ),
            {
                "signal_type": signal.signal_type,
                "source": signal.source,
                "raw_snapshot_id": signal.raw_snapshot_id,
                "value": json.dumps(signal.value),
                # asyncpg binds TIMESTAMPTZ params by native datetime, not
                # by ISO string -- Signal.observed_at is a string (INV-15
                # keeps the fact tuple JSON-serializable), parsed here at
                # the storage boundary.
                "observed_at": datetime.fromisoformat(signal.observed_at),
                "ttl_class": signal.ttl_class,
                "confidence": signal.confidence,
                "object_customer": signal.object_customer,
                "object_region": signal.object_region,
                "object_project_type": signal.object_project_type,
                "correlation_id": signal.correlation_id,
            },
        )
    ).scalar_one()


async def list_signals(conn: AsyncConnection, *, signal_type: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
                           confidence, object_customer, object_region, object_project_type, correlation_id
                    FROM signals WHERE signal_type = :signal_type ORDER BY id
                    """
                ),
                {"signal_type": signal_type},
            )
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        row_dict = dict(row)
        if isinstance(row_dict["value"], str):
            row_dict["value"] = json.loads(row_dict["value"])
        result.append(row_dict)
    return result


async def list_signals_by_object_region(conn: AsyncConnection, *, object_region: str) -> list[dict[str, Any]]:
    """TENDER_INTELLIGENCE_SPEC.md §5.3's "накопленные сигналы" (accumulated
    signals) primitive: every signal about one real object, across all
    signal_types, ordered by when it was observed -- unlike list_signals,
    which filters by type."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
                           confidence, object_customer, object_region, object_project_type, correlation_id
                    FROM signals WHERE object_region = :object_region ORDER BY observed_at
                    """
                ),
                {"object_region": object_region},
            )
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        row_dict = dict(row)
        if isinstance(row_dict["value"], str):
            row_dict["value"] = json.loads(row_dict["value"])
        result.append(row_dict)
    return result


async def detect_object_region_intersection(conn: AsyncConnection, *, object_region: str) -> ObjectIntersection:
    """TENDER_INTELLIGENCE_SPEC.md §5.3 / P310's own definition of a real
    forecast trigger -- an intersection of independent signal_types on one
    object, not a single signal. Composes list_signals_by_object_region's
    real accumulated rows with object_intersection.py's pure classifier;
    does not itself assign a weak/medium/strong tier or apply TTL decay --
    both remain blocked on TBD-TIS-02/TBD-TIS-01 (see OPEN-QUESTIONS.md)."""
    rows = await list_signals_by_object_region(conn, object_region=object_region)
    return detect_intersection(object_region, rows)


async def build_object_region_forecast_card(conn: AsyncConnection, *, object_region: str) -> ForecastCard | None:
    """TENDER_INTELLIGENCE_SPEC.md §5.4 / P311: assembles a forecast card's
    real evidence chain for one object, gated on the same is_composite
    fact detect_object_region_intersection already proves -- see
    forecast_card.py's own docstring for what is and isn't built here."""
    rows = await list_signals_by_object_region(conn, object_region=object_region)
    return build_forecast_card(object_region, rows)
