"""The real, versioned network API contract between apps/api_tender and
apps/api_vendor (ADR-0006) -- packages/contracts' first real module. This
is deliberately a real httpx-based HTTP client, not an in-process function
call: it has real timeout/network-failure handling, because the two sides
are now separate deployable processes, not packages sharing one process.

Forwards the caller's ambient correlation id (packages/platform/
correlation.py's ContextVar, set by CorrelationIdMiddleware for the
current inbound request) as the X-Correlation-Id header -- the receiving
service's own CorrelationIdMiddleware instance already reads that header
on the way in (confirmed by reading its source; no changes needed there),
so correlation ids thread across the service boundary the same way they
already thread API -> worker -> outbox within one process (NFR-OBS-01)."""

from __future__ import annotations

from datetime import datetime

import httpx
from pydantic import BaseModel, ValidationError

from packages.platform.correlation import CORRELATION_ID_HEADER, get_correlation_id_or_none


class VendorPingResponse(BaseModel):
    service: str
    status: str


class VendorApiError(Exception):
    """Any failure calling the vendor service: unreachable, non-200, or a
    response that doesn't match the contract -- always this one typed
    error, never a bare httpx/pydantic exception leaking to the caller."""


async def ping_vendor_service(
    base_url: str,
    *,
    correlation_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> VendorPingResponse:
    resolved_correlation_id = correlation_id or get_correlation_id_or_none()
    headers = {CORRELATION_ID_HEADER: resolved_correlation_id} if resolved_correlation_id else {}

    owns_client = client is None
    http_client = client or httpx.AsyncClient()
    try:
        response = await http_client.get(f"{base_url}/internal/ping", headers=headers, timeout=10.0)
    except httpx.HTTPError as exc:
        raise VendorApiError(f"vendor service unreachable: {exc}") from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code != 200:
        raise VendorApiError(f"vendor service returned status {response.status_code}: {response.text}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise VendorApiError(f"vendor service returned non-JSON response: {exc}") from exc

    try:
        return VendorPingResponse.model_validate(payload)
    except ValidationError as exc:
        raise VendorApiError(f"vendor service response does not match contract: {exc}") from exc


class VendorOfferDTO(BaseModel):
    id: int
    vendor_id: int
    vendor_name: str
    data_realm: str
    watermark: str
    material: str
    price: float
    currency: str
    vat_rate: float
    uom: str
    uom_canonical_qty: float
    moq: float
    capacity: float
    inventory: float
    valid_from: datetime
    valid_until: datetime
    evidence_source: str
    observed_at: datetime
    adverse_case: str | None
    executable_status: str
    effective_executable_status: str
    has_positive_reputation: bool
    has_negative_reputation: bool


class _VendorOfferListPayload(BaseModel):
    items: list[VendorOfferDTO]


async def list_vendor_offers(
    base_url: str,
    *,
    data_realm: str,
    as_of: str,
    correlation_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> list[VendorOfferDTO]:
    resolved_correlation_id = correlation_id or get_correlation_id_or_none()
    headers = {CORRELATION_ID_HEADER: resolved_correlation_id} if resolved_correlation_id else {}

    owns_client = client is None
    http_client = client or httpx.AsyncClient()
    try:
        response = await http_client.get(
            f"{base_url}/internal/offers",
            params={"data_realm": data_realm, "as_of": as_of},
            headers=headers,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise VendorApiError(f"vendor service unreachable: {exc}") from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code != 200:
        raise VendorApiError(f"vendor service returned status {response.status_code}: {response.text}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise VendorApiError(f"vendor service returned non-JSON response: {exc}") from exc

    try:
        return _VendorOfferListPayload.model_validate(payload).items
    except ValidationError as exc:
        raise VendorApiError(f"vendor service response does not match contract: {exc}") from exc
