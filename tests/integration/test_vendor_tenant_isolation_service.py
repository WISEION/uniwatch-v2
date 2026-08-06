"""Service-level proof for FR-VND-09 (PRD §5.5/§9.2): packages/vendor's
own list_offers_by_vendor() function -- the service layer's public API
for reading one vendor's offers -- never returns another vendor's rows,
called directly (no HTTP, no raw SQL), with two vendors' real synthetic
generator output stored side by side."""

from __future__ import annotations

from packages.vendor.synthetic_provider import SyntheticProvider
from packages.vendor.vendor_store import list_offers_by_vendor, store_offer, store_vendor

AS_OF = "2026-08-06T00:00:00+00:00"


async def test_list_offers_by_vendor_never_returns_another_vendors_offers(engine):
    vendors_a, offers_a = SyntheticProvider(seed=101).generate(as_of=AS_OF)
    vendors_b, offers_b = SyntheticProvider(seed=102).generate(as_of=AS_OF)

    async with engine.begin() as conn:
        ids_a: dict[str, int] = {}
        for vendor in vendors_a:
            vendor_id, _api_key = await store_vendor(conn, vendor)
            ids_a[vendor.name] = vendor_id
        for offer in offers_a:
            await store_offer(conn, ids_a[offer.vendor_name], offer)

        ids_b: dict[str, int] = {}
        for vendor in vendors_b:
            vendor_id, _api_key = await store_vendor(conn, vendor)
            ids_b[vendor.name] = vendor_id
        for offer in offers_b:
            await store_offer(conn, ids_b[offer.vendor_name], offer)

        # Ask for one specific vendor from seed=101's batch.
        one_vendor_id = next(iter(ids_a.values()))
        rows = await list_offers_by_vendor(conn, vendor_id=one_vendor_id)

    assert len(rows) > 0
    assert all(row["vendor_id"] == one_vendor_id for row in rows)
    assert all(row["vendor_id"] not in ids_b.values() for row in rows)
