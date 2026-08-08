"""Integration test for GET /internal/offers' cursor pagination
(FR-PLT-05, closed 2026-08-08 -- was previously unbounded, see
docs/decisions/OPEN-QUESTIONS.md 2026-08-06). Same real-page-boundary
discipline as tests/integration/test_bom_lines_pagination.py's P002 proof:
this asserts actual cursor-to-cursor traversal over real rows, not just
that a `next_cursor` field exists somewhere in the response shape."""

from __future__ import annotations

import httpx

from apps.api_vendor.main import create_app as create_vendor_app
from packages.platform.settings import Settings
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor


async def test_internal_offers_pagination_traverses_all_pages_without_gaps_or_dupes(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=13)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor = Vendor(
            data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Pagination Vendor", provider_type="synthetic", seed=1
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer_ids = []
        for i in range(3):
            offer = Offer(
                vendor_name="Pagination Vendor",
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material=f"material-{i}",
                price=100.0 + i,
                currency="AZN",
                vat_rate=0.18,
                uom="t",
                uom_canonical_qty=1.0,
                moq=1.0,
                capacity=10.0,
                inventory=5.0,
                valid_from="2026-08-01T00:00:00+00:00",
                valid_until="2026-09-01T00:00:00+00:00",
                evidence_source="test",
                observed_at="2026-08-06T00:00:00+00:00",
                adverse_case=None,
                executable_status="reported",
            )
            offer_ids.append(await store_offer(conn, vendor_id, offer))

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        page1 = (
            await client.get(
                "/internal/offers",
                params={"data_realm": "vendor-sandbox", "as_of": "2026-08-06T00:00:00+00:00", "limit": 2},
            )
        ).json()
        assert len(page1["items"]) == 2
        assert page1["next_cursor"] is not None

        page2 = (
            await client.get(
                "/internal/offers",
                params={
                    "data_realm": "vendor-sandbox",
                    "as_of": "2026-08-06T00:00:00+00:00",
                    "limit": 2,
                    "cursor": page1["next_cursor"],
                },
            )
        ).json()

    assert len(page2["items"]) == 1
    assert page2["next_cursor"] is None
    seen_ids = [item["id"] for item in page1["items"]] + [item["id"] for item in page2["items"]]
    assert sorted(seen_ids) == sorted(offer_ids)
    assert len(set(seen_ids)) == 3


async def test_internal_offers_default_limit_returns_no_next_cursor_when_under_page_size(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=13)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor = Vendor(
            data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Single Page Vendor", provider_type="synthetic", seed=2
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Single Page Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="cement M400",
            price=100.0,
            currency="AZN",
            vat_rate=0.18,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=10.0,
            inventory=5.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-06T00:00:00+00:00",
            adverse_case=None,
            executable_status="reported",
        )
        await store_offer(conn, vendor_id, offer)

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        response = await client.get(
            "/internal/offers",
            params={"data_realm": "vendor-sandbox", "as_of": "2026-08-06T00:00:00+00:00"},
        )

    payload = response.json()
    assert payload["next_cursor"] is None
    assert any(item["vendor_id"] == vendor_id for item in payload["items"])
