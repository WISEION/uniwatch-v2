"""Real proof that the vendors/vendor_offers schema exists and that its
realm/watermark CHECK constraint is a real database-level guarantee
(FR-VND-06, ADR-0004), not just an application-code convention."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


async def test_vendors_table_rejects_realm_watermark_mismatch(engine):
    async with engine.begin() as conn:
        # Correct pairing succeeds.
        await conn.execute(
            text(
                "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Test Vendor', 'synthetic', 1, 'test-key-1')"
            )
        )

    async with engine.begin() as conn:
        try:
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'REAL', 'Bad Vendor', 'synthetic', 1, 'test-key-2')"
                )
            )
        except IntegrityError:
            pass
        else:
            raise AssertionError("expected a realm/watermark mismatch to be rejected by the database")


async def test_vendor_offers_table_rejects_realm_watermark_mismatch(engine):
    async with engine.begin() as conn:
        vendor_id = (
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Test Vendor 2', 'synthetic', 2, 'test-key-3') RETURNING id"
                )
            )
        ).scalar_one()

    async with engine.begin() as conn:
        try:
            await conn.execute(
                text(
                    "INSERT INTO vendor_offers "
                    "(vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom, "
                    " uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until, "
                    " evidence_source, observed_at) "
                    "VALUES (:vendor_id, 'vendor-sandbox', 'REAL', 'rebar', 850.0, 'AZN', 18.0, 'ton', "
                    " 1.0, 5.0, 100.0, 80.0, now(), now(), 'test', now())"
                ),
                {"vendor_id": vendor_id},
            )
        except IntegrityError:
            pass
        else:
            raise AssertionError("expected a realm/watermark mismatch to be rejected by the database")
