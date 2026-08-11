"""Route-level proof for FR-VND-09 (PRD §5.5/§9.2, INV-08): a real HTTP
request to GET /vendors/me/offers, authenticated with vendor A's own
API key, never returns vendor B's offers -- and a request with no key,
or an unknown key, is denied (401), never given a default identity."""

from __future__ import annotations

import httpx
import pytest_asyncio

from apps.api_vendor.main import create_app
from packages.platform.settings import Settings
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor

AS_OF = "2026-08-06T00:00:00+00:00"


@pytest_asyncio.fixture
async def client(engine, _database_url, migrated_asyncpg_dsn):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as c:
        yield c


def _offer(vendor_name: str, material: str) -> Offer:
    return Offer(
        vendor_name=vendor_name,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material=material,
        price=100.0,
        currency="AZN",
        vat_rate=18.0,
        uom="ton",
        uom_canonical_qty=1.0,
        moq=1.0,
        capacity=10.0,
        inventory=5.0,
        valid_from=AS_OF,
        valid_until="2026-12-31T00:00:00+00:00",
        evidence_source="route-isolation-test",
        observed_at=AS_OF,
        adverse_case=None,
        executable_status="confirmed",
    )


async def test_a_vendor_only_sees_its_own_offers(client, engine):
    vendor_a = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Route Tenant A", provider_type="synthetic", seed=201
    )
    vendor_b = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Route Tenant B", provider_type="synthetic", seed=202
    )

    async with engine.begin() as conn:
        vendor_a_id, key_a = await store_vendor(conn, vendor_a)
        vendor_b_id, _key_b = await store_vendor(conn, vendor_b)
        await store_offer(conn, vendor_a_id, _offer("Route Tenant A", "rebar-16mm"))
        await store_offer(conn, vendor_b_id, _offer("Route Tenant B", "cement-42.5"))

    response = await client.get("/vendors/me/offers", headers={"X-Vendor-Api-Key": key_a})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["vendor_id"] == vendor_a_id
    assert body["items"][0]["material"] == "rebar-16mm"
    assert all(item["vendor_id"] != vendor_b_id for item in body["items"])


async def test_missing_api_key_is_denied_not_defaulted(client):
    response = await client.get("/vendors/me/offers")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_unknown_api_key_is_denied_not_defaulted(client):
    response = await client.get("/vendors/me/offers", headers={"X-Vendor-Api-Key": "not-a-real-key"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
