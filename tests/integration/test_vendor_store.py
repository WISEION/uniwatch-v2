"""Real proof that the synthetic provider's output round-trips through
the database unchanged, and that a full sandbox-realm generation run
produces only sandbox/SYNTHETIC rows when queried back
(FR-VND-01, FR-VND-06)."""

from __future__ import annotations

from packages.vendor.synthetic_provider import SyntheticProvider
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import (
    get_vendor_id_by_api_key,
    list_offers_by_data_realm,
    list_offers_with_vendor_name_by_data_realm,
    store_offer,
    store_vendor,
)

AS_OF = "2026-08-06T00:00:00+00:00"


async def test_synthetic_generation_round_trips_through_the_database(engine):
    vendors, offers = SyntheticProvider(seed=7).generate(as_of=AS_OF)

    async with engine.begin() as conn:
        vendor_ids = {}
        for vendor in vendors:
            vendor_ids[vendor.name], _api_key = await store_vendor(conn, vendor)
        for offer in offers:
            await store_offer(conn, vendor_ids[offer.vendor_name], offer)

        rows = await list_offers_by_data_realm(conn, data_realm="vendor-sandbox")

    assert len(rows) == 8
    assert all(row["watermark"] == "SYNTHETIC" for row in rows)
    assert {row["adverse_case"] for row in rows} == {
        None,
        "stale_offer",
        "moq_conflict",
        "mixed_uom",
        "currency_vat_mismatch",
        "capacity_shortfall",
        "expiring_evidence",
        "partial_fulfillment",
    }
    stale_row = next(row for row in rows if row["adverse_case"] == "stale_offer")
    assert stale_row["material"] == "cement-42.5"


async def test_no_production_realm_rows_exist_after_a_synthetic_run(engine):
    vendors, offers = SyntheticProvider(seed=8).generate(as_of=AS_OF)

    async with engine.begin() as conn:
        vendor_ids = {}
        for vendor in vendors:
            vendor_ids[vendor.name], _api_key = await store_vendor(conn, vendor)
        for offer in offers:
            await store_offer(conn, vendor_ids[offer.vendor_name], offer)

        production_rows = await list_offers_by_data_realm(conn, data_realm="vendor-production")

    assert production_rows == []


async def test_store_vendor_issues_a_unique_server_generated_api_key(engine):
    vendor_a = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="A", provider_type="synthetic", seed=1)
    vendor_b = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="B", provider_type="synthetic", seed=2)

    async with engine.begin() as conn:
        _id_a, key_a = await store_vendor(conn, vendor_a)
        _id_b, key_b = await store_vendor(conn, vendor_b)

    assert key_a != key_b
    assert key_a and key_b  # never empty


async def test_get_vendor_id_by_api_key_resolves_the_right_vendor(engine):
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="C", provider_type="synthetic", seed=3)

    async with engine.begin() as conn:
        vendor_id, api_key = await store_vendor(conn, vendor)
        resolved = await get_vendor_id_by_api_key(conn, api_key=api_key)

    assert resolved == vendor_id


async def test_get_vendor_id_by_api_key_denies_an_unknown_key(engine):
    async with engine.begin() as conn:
        resolved = await get_vendor_id_by_api_key(conn, api_key="not-a-real-key")

    assert resolved is None


async def test_list_offers_with_vendor_name_by_data_realm_includes_vendor_name(engine):
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Joined Vendor", provider_type="synthetic", seed=1)
    offer = Offer(
        vendor_name="Joined Vendor",
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material="rebar A400",
        price=850.0,
        currency="AZN",
        vat_rate=0.18,
        uom="t",
        uom_canonical_qty=1.0,
        moq=1.0,
        capacity=50.0,
        inventory=20.0,
        valid_from="2026-08-01T00:00:00+00:00",
        valid_until="2026-09-01T00:00:00+00:00",
        evidence_source="test",
        observed_at="2026-08-06T00:00:00+00:00",
        adverse_case=None,
        executable_status="confirmed",
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_offer(conn, vendor_id, offer)
        rows = await list_offers_with_vendor_name_by_data_realm(conn, data_realm="vendor-sandbox")

    matching = [r for r in rows if r["vendor_id"] == vendor_id]
    assert len(matching) == 1
    assert matching[0]["vendor_name"] == "Joined Vendor"
    assert matching[0]["material"] == "rebar A400"
    assert matching[0]["executable_status"] == "confirmed"
