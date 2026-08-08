"""Vendor synthetic-sandbox persistence (FR-VND-01, FR-VND-06). Same
append-friendly, explicit-realm discipline as
packages/tender/signals_store.py -- every insert carries data_realm and
watermark explicitly (the database's own CHECK constraint,
migrations/0009_vendor_sandbox.sql, is the real enforcement; this module
does not re-validate it, it just never omits the columns)."""

from __future__ import annotations

import secrets
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .vendor_model import Offer, Vendor


async def store_vendor(conn: AsyncConnection, vendor: Vendor) -> tuple[int, str]:
    api_key = secrets.token_hex(32)
    vendor_id = (
        await conn.execute(
            text(
                """
                INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key)
                VALUES (:data_realm, :watermark, :name, :provider_type, :seed, :api_key)
                RETURNING id
                """
            ),
            {
                "data_realm": vendor.data_realm,
                "watermark": vendor.watermark,
                "name": vendor.name,
                "provider_type": vendor.provider_type,
                "seed": vendor.seed,
                "api_key": api_key,
            },
        )
    ).scalar_one()
    return vendor_id, api_key


async def store_offer(conn: AsyncConnection, vendor_id: int, offer: Offer) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendor_offers
                    (vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom,
                     uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                     evidence_source, observed_at, adverse_case, executable_status)
                VALUES (:vendor_id, :data_realm, :watermark, :material, :price, :currency, :vat_rate, :uom,
                        :uom_canonical_qty, :moq, :capacity, :inventory, :valid_from, :valid_until,
                        :evidence_source, :observed_at, :adverse_case, :executable_status)
                RETURNING id
                """
            ),
            {
                "vendor_id": vendor_id,
                "data_realm": offer.data_realm,
                "watermark": offer.watermark,
                "material": offer.material,
                "price": offer.price,
                "currency": offer.currency,
                "vat_rate": offer.vat_rate,
                "uom": offer.uom,
                "uom_canonical_qty": offer.uom_canonical_qty,
                "moq": offer.moq,
                "capacity": offer.capacity,
                "inventory": offer.inventory,
                # asyncpg binds TIMESTAMPTZ params by native datetime, not by
                # ISO string -- Offer's date fields are strings (same
                # JSON-serializable-fact-tuple discipline as Signal.observed_at
                # in packages/tender/signals_store.py), parsed here at the
                # storage boundary.
                "valid_from": datetime.fromisoformat(offer.valid_from),
                "valid_until": datetime.fromisoformat(offer.valid_until),
                "evidence_source": offer.evidence_source,
                "observed_at": datetime.fromisoformat(offer.observed_at),
                "adverse_case": offer.adverse_case,
                "executable_status": offer.executable_status,
            },
        )
    ).scalar_one()


async def list_offers_by_data_realm(conn: AsyncConnection, *, data_realm: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, vendor_id, data_realm, watermark, material, price, currency, vat_rate,
                           uom, uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                           evidence_source, observed_at, adverse_case, executable_status
                    FROM vendor_offers WHERE data_realm = :data_realm ORDER BY id
                    """
                ),
                {"data_realm": data_realm},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def get_vendor_id_by_api_key(conn: AsyncConnection, *, api_key: str) -> int | None:
    row = (await conn.execute(text("SELECT id FROM vendors WHERE api_key = :api_key"), {"api_key": api_key})).first()
    return row[0] if row is not None else None


async def list_offers_by_vendor(conn: AsyncConnection, *, vendor_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, vendor_id, data_realm, watermark, material, price, currency, vat_rate,
                           uom, uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                           evidence_source, observed_at, adverse_case, executable_status
                    FROM vendor_offers WHERE vendor_id = :vendor_id ORDER BY id
                    """
                ),
                {"vendor_id": vendor_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def list_offers_with_vendor_name_by_data_realm(
    conn: AsyncConnection, *, data_realm: str, after_id: int = 0, limit: int = 100
) -> list[dict[str, Any]]:
    """Same shape as list_offers_by_data_realm, plus vendor_name -- lets a
    caller outside this service (packages/decision, via the internal
    offers endpoint) resolve vendor identity in one round trip.

    Opaque cursor pagination (FR-PLT-05, packages/platform/pagination.py's
    convention): `after_id`/`limit` fetch limit+1 rows by id order so the
    caller can tell whether another page exists without a separate COUNT
    query."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT o.id, o.vendor_id, v.name AS vendor_name, o.data_realm, o.watermark, o.material,
                           o.price, o.currency, o.vat_rate, o.uom, o.uom_canonical_qty, o.moq, o.capacity,
                           o.inventory, o.valid_from, o.valid_until, o.evidence_source, o.observed_at, o.adverse_case,
                           o.executable_status
                    FROM vendor_offers o
                    JOIN vendors v ON v.id = o.vendor_id
                    WHERE o.data_realm = :data_realm AND o.id > :after_id
                    ORDER BY o.id
                    LIMIT :limit_plus_one
                    """
                ),
                {"data_realm": data_realm, "after_id": after_id, "limit_plus_one": limit + 1},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
