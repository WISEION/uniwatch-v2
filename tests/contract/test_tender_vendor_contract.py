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
from packages.contracts.vendor_api import VendorPingResponse, ping_vendor_service
from packages.platform.correlation import bind_correlation_id
from packages.platform.settings import Settings


async def test_ping_vendor_service_round_trip_against_the_real_vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=11)
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
    settings = Settings(database_url=_database_url, expected_schema_version=11)
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
