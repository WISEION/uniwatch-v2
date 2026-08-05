"""Unit tests for packages/contracts/vendor_api.py -- the real network API
contract between apps/api_tender and apps/api_vendor (ADR-0006). Pure unit
tests: httpx.MockTransport stands in for a real vendor service, no DB, no
real network, no real apps/api_vendor app needed here (that end-to-end
proof is tests/contract/test_tender_vendor_contract.py)."""

from __future__ import annotations

import httpx
import pytest

from packages.contracts.vendor_api import VendorApiError, VendorPingResponse, ping_vendor_service
from packages.platform.correlation import bind_correlation_id


async def test_ping_vendor_service_returns_parsed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"service": "vendor", "status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        result = await ping_vendor_service("http://vendor-test", client=client)

    assert result == VendorPingResponse(service="vendor", status="ok")


async def test_ping_vendor_service_sends_ambient_correlation_id_header():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-correlation-id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={"service": "vendor", "status": "ok"})

    transport = httpx.MockTransport(handler)
    bind_correlation_id("corr-unit-test-1")
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await ping_vendor_service("http://vendor-test", client=client)

    assert captured["x-correlation-id"] == "corr-unit-test-1"


async def test_ping_vendor_service_explicit_correlation_id_overrides_ambient():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-correlation-id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={"service": "vendor", "status": "ok"})

    transport = httpx.MockTransport(handler)
    bind_correlation_id("corr-ambient")
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await ping_vendor_service("http://vendor-test", correlation_id="corr-explicit", client=client)

    assert captured["x-correlation-id"] == "corr-explicit"


async def test_ping_vendor_service_raises_typed_error_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await ping_vendor_service("http://vendor-test", client=client)


async def test_ping_vendor_service_raises_typed_error_on_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await ping_vendor_service("http://vendor-test", client=client)


async def test_ping_vendor_service_raises_typed_error_on_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await ping_vendor_service("http://vendor-test", client=client)
