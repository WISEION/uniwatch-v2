"""Unit tests for packages/contracts/vendor_api.py -- the real network API
contract between apps/api_tender and apps/api_vendor (ADR-0006). Pure unit
tests: httpx.MockTransport stands in for a real vendor service, no DB, no
real network, no real apps/api_vendor app needed here (that end-to-end
proof is tests/contract/test_tender_vendor_contract.py)."""

from __future__ import annotations

import httpx
import pytest

from packages.contracts.vendor_api import VendorApiError, VendorPingResponse, list_vendor_offers, ping_vendor_service
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


async def test_list_vendor_offers_returns_parsed_items():
    payload = {
        "items": [
            {
                "id": 1,
                "vendor_id": 7,
                "vendor_name": "Reliable Vendor",
                "data_realm": "vendor-sandbox",
                "watermark": "SYNTHETIC",
                "material": "cement M400",
                "price": 120.0,
                "currency": "AZN",
                "vat_rate": 0.18,
                "uom": "t",
                "uom_canonical_qty": 1.0,
                "moq": 1.0,
                "capacity": 100.0,
                "inventory": 40.0,
                "valid_from": "2026-08-01T00:00:00+00:00",
                "valid_until": "2026-09-01T00:00:00+00:00",
                "evidence_source": "test",
                "observed_at": "2026-08-06T00:00:00+00:00",
                "adverse_case": None,
                "executable_status": "reserved",
                "effective_executable_status": "reserved",
                "has_positive_reputation": True,
                "has_negative_reputation": False,
            }
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        result = await list_vendor_offers(
            "http://vendor-test", data_realm="vendor-sandbox", as_of="2026-08-06T00:00:00+00:00", client=client
        )

    assert len(result) == 1
    assert result[0].vendor_name == "Reliable Vendor"
    assert result[0].has_positive_reputation is True


async def test_list_vendor_offers_sends_query_params():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["data_realm"] = request.url.params.get("data_realm")
        captured["as_of"] = request.url.params.get("as_of")
        return httpx.Response(200, json={"items": []})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await list_vendor_offers(
            "http://vendor-test", data_realm="vendor-sandbox", as_of="2026-08-06T00:00:00+00:00", client=client
        )

    assert captured["data_realm"] == "vendor-sandbox"
    assert captured["as_of"] == "2026-08-06T00:00:00+00:00"


async def test_list_vendor_offers_raises_typed_error_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await list_vendor_offers(
                "http://vendor-test", data_realm="vendor-sandbox", as_of="2026-08-06T00:00:00+00:00", client=client
            )
