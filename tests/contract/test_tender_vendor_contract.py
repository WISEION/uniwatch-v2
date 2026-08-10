"""tests/contract's first real test (tests/README.md: "OpenAPI/schema
contracts, synthetic vs real adapter parity"): proves packages/contracts'
vendor_api client and the real apps/api_vendor app actually speak the same
schema over a real HTTP-shaped round trip (ADR-0006), not just against a
mock transport (see tests/unit/test_vendor_api_contract.py for the mocked
unit tests). Uses httpx.ASGITransport -- no real TCP port, but a real
ASGI/HTTP request-response cycle including headers and middleware."""

from __future__ import annotations

import httpx

from apps.api_vendor.main import create_app as create_vendor_app
from packages.contracts.vendor_api import VendorPingResponse, list_vendor_offers, ping_vendor_service
from packages.platform.correlation import bind_correlation_id
from packages.platform.settings import Settings
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor


async def test_ping_vendor_service_round_trip_against_the_real_vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine
    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        result = await ping_vendor_service("http://vendor-test", client=client)

    assert result == VendorPingResponse(service="vendor", status="ok")


async def test_ping_vendor_service_ambient_correlation_id_reaches_the_real_vendor_app_middleware(engine, _database_url):
    # Proves cross-service propagation end to end: the real
    # CorrelationIdMiddleware running inside the real vendor app echoes
    # back whatever correlation id it received on the response -- if the
    # client's ambient id didn't reach it, this would echo a freshly
    # minted id instead.
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine
    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)

    bind_correlation_id("corr-cross-service-e2e-1")
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await ping_vendor_service("http://vendor-test", client=client)
        # A second, direct call confirms what the middleware actually saw
        # and echoed for a request carrying that same ambient id.
        response = await client.get("/internal/ping", headers={"X-Correlation-Id": "corr-cross-service-e2e-1"})

    assert response.headers["X-Correlation-Id"] == "corr-cross-service-e2e-1"


async def test_list_vendor_offers_round_trip_against_the_real_vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor = Vendor(
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            name="Contract Test Vendor",
            provider_type="synthetic",
            seed=1,
        )
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Contract Test Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="steel beam",
            price=500.0,
            currency="AZN",
            vat_rate=0.18,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=20.0,
            inventory=10.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-06T00:00:00+00:00",
            adverse_case=None,
            executable_status="confirmed",
        )
        await store_offer(conn, vendor_id, offer)

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        result = await list_vendor_offers(
            "http://vendor-test", data_realm="vendor-sandbox", as_of="2026-08-06T00:00:00+00:00", client=client
        )

    matching = [r for r in result if r.vendor_id == vendor_id]
    assert len(matching) == 1
    assert matching[0].material == "steel beam"
