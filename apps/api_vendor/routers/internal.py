"""Internal, service-to-service endpoints for the Vendor service (ADR-0006).
`GET /internal/ping` is deliberately trivial and unauthenticated -- it
proves the tender<->vendor real-API-contract mechanism (packages/contracts)
works end to end, without inventing real vendor business data
(packages/vendor has no domain code yet, synthetic-only pre-legal-gate).

`GET /internal/offers` (task 3.D prep, TENDER_INTELLIGENCE_SPEC.md §6.4) is
the one endpoint packages/decision's cross-domain matching logic consumes
through packages/contracts/vendor_api.py -- it never reads packages/vendor's
tables directly. Reputation flags are computed here, not by the caller,
because this service already has authoritative access to both
vendor_offers and vendor_reputation_facts; a per-vendor round trip from the
caller would be pure ceremony for no isolation benefit within one service.

Deliberately UNAUTHENTICATED, same gap as /internal/ping: real
service-to-service auth is deferred by ADR-0006 to the still-open
D-IDP/D-HOST decisions -- recorded in docs/decisions/OPEN-QUESTIONS.md, not
silently assumed secure."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.vendor.reputation_model import NEGATIVE_EVENT_TYPES, POSITIVE_EVENT_TYPES
from packages.vendor.reputation_store import list_active_reputation_facts
from packages.vendor.vendor_store import list_offers_with_vendor_name_by_data_realm

from ..deps import get_connection

router = APIRouter(tags=["internal"])


class PingResponse(BaseModel):
    service: str
    status: str


@router.get("/internal/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(service="vendor", status="ok")


class InternalOfferResponse(BaseModel):
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
    has_positive_reputation: bool
    has_negative_reputation: bool


class InternalOfferListResponse(BaseModel):
    items: list[InternalOfferResponse]


@router.get("/internal/offers", response_model=InternalOfferListResponse)
async def list_internal_offers(
    data_realm: str,
    as_of: datetime,
    conn: AsyncConnection = Depends(get_connection),
) -> InternalOfferListResponse:
    rows = await list_offers_with_vendor_name_by_data_realm(conn, data_realm=data_realm)
    reputation_cache: dict[int, tuple[bool, bool]] = {}
    items: list[InternalOfferResponse] = []
    as_of_iso = as_of.isoformat()
    for row in rows:
        vendor_id = row["vendor_id"]
        if vendor_id not in reputation_cache:
            facts = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of=as_of_iso)
            event_types = {f["event_type"] for f in facts}
            has_positive = any(t in POSITIVE_EVENT_TYPES for t in event_types)
            has_negative = any(t in NEGATIVE_EVENT_TYPES for t in event_types)
            reputation_cache[vendor_id] = (has_positive, has_negative)
        has_positive, has_negative = reputation_cache[vendor_id]
        items.append(
            InternalOfferResponse(
                **row,
                has_positive_reputation=has_positive,
                has_negative_reputation=has_negative,
            )
        )
    return InternalOfferListResponse(items=items)
