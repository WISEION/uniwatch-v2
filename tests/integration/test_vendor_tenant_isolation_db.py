"""Database-level proof for FR-VND-09 (PRD §5.5/§9.2): filtering
vendor_offers by vendor_id at the SQL layer itself -- not through any
packages/vendor Python function -- never returns another vendor's rows,
even when both vendors' offers physically coexist in the same table with
otherwise-identical field values (same material/price/currency), so the
only thing that could distinguish them is vendor_id itself."""

from __future__ import annotations

from sqlalchemy import text


async def test_raw_sql_scoped_by_vendor_id_never_returns_another_vendors_offers(engine):
    async with engine.begin() as conn:
        vendor_a_id = (
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Tenant A', 'synthetic', 1, 'db-test-key-a') "
                    "RETURNING id"
                )
            )
        ).scalar_one()
        vendor_b_id = (
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Tenant B', 'synthetic', 2, 'db-test-key-b') "
                    "RETURNING id"
                )
            )
        ).scalar_one()

        # Identical fields on both offers except vendor_id -- vendor_id is
        # the *only* thing a scoped query could rely on.
        for vendor_id in (vendor_a_id, vendor_b_id):
            await conn.execute(
                text(
                    "INSERT INTO vendor_offers "
                    "(vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom, "
                    " uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until, "
                    " evidence_source, observed_at, executable_status) "
                    "VALUES (:vendor_id, 'vendor-sandbox', 'SYNTHETIC', 'rebar-16mm', 870.5, 'AZN', 18.0, 'ton', "
                    " 1.0, 5.0, 150.0, 90.0, now(), now(), 'db-isolation-test', now(), 'confirmed')"
                ),
                {"vendor_id": vendor_id},
            )

        rows_for_a = (
            (
                await conn.execute(
                    text("SELECT vendor_id FROM vendor_offers WHERE vendor_id = :vendor_id"),
                    {"vendor_id": vendor_a_id},
                )
            )
            .mappings()
            .all()
        )

    assert len(rows_for_a) == 1
    assert rows_for_a[0]["vendor_id"] == vendor_a_id
    assert rows_for_a[0]["vendor_id"] != vendor_b_id
