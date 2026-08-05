"""Vendor synthetic-sandbox persistence (FR-VND-01, FR-VND-06). Same
append-friendly, explicit-realm discipline as
packages/tender/signals_store.py -- every insert carries data_realm and
watermark explicitly (the database's own CHECK constraint,
migrations/0009_vendor_sandbox.sql, is the real enforcement; this module
does not re-validate it, it just never omits the columns)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .vendor_model import Offer, Vendor


async def store_vendor(conn: AsyncConnection, vendor: Vendor) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendors (data_realm, watermark, name, provider_type, seed)
                VALUES (:data_realm, :watermark, :name, :provider_type, :seed)
                RETURNING id
                """
            ),
            {
                "data_realm": vendor.data_realm,
                "watermark": vendor.watermark,
                "name": vendor.name,
                "provider_type": vendor.provider_type,
                "seed": vendor.seed,
            },
        )
    ).scalar_one()


async def store_offer(conn: AsyncConnection, vendor_id: int, offer: Offer) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendor_offers
                    (vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom,
                     uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                     evidence_source, observed_at, adverse_case)
                VALUES (:vendor_id, :data_realm, :watermark, :material, :price, :currency, :vat_rate, :uom,
                        :uom_canonical_qty, :moq, :capacity, :inventory, :valid_from, :valid_until,
                        :evidence_source, :observed_at, :adverse_case)
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
                           evidence_source, observed_at, adverse_case
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
