"""Internal, service-to-service endpoints for the Vendor service (ADR-0006).
`GET /internal/ping` is deliberately trivial and unauthenticated -- it
proves the tender<->vendor real-API-contract mechanism (packages/contracts)
works end to end, without inventing real vendor business data
(packages/vendor has no domain code yet, synthetic-only pre-legal-gate).

`GET /internal/offers` (task 3.D prep, TENDER_INTELLIGENCE_SPEC.md §6.4) is
the one endpoint packages/decision's cross-domain matching logic consumes
through packages/contracts/vendor_api.py -- it never reads packages/vendor's
tables directly. Reputation flags -- and, as of task 3.C, the reputation-weighted
`effective_executable_status` (TENDER_INTELLIGENCE_SPEC.md §6.3, P314) --
are computed here, not by the caller, because this service already has
authoritative access to both vendor_offers and vendor_reputation_facts; a
per-vendor round trip from the caller would be pure ceremony for no
isolation benefit within one service. The response carries both the raw
`executable_status` (the vendor's own declared/observed tier) and the
computed `effective_executable_status`, never collapsing the two into one
field -- a caller that only wants the raw fact should never be forced to
also swallow the reputation weighting, and vice versa.

Cursor pagination (FR-PLT-05, packages/platform/pagination.py): `cursor`/
`limit` follow the same opaque-cursor-by-id convention as
apps/api_tender/routers/admin_users.py's `list_users` -- CLAUDE.md's rule
to apply pagination.py to any new listing endpoint, closed here (was
previously unbounded, recorded as a deferred gap in
docs/decisions/OPEN-QUESTIONS.md, 2026-08-06).

Deliberately UNAUTHENTICATED, same gap as /internal/ping: real
service-to-service auth is deferred by ADR-0006 to the still-open
D-IDP/D-HOST decisions -- recorded in docs/decisions/OPEN-QUESTIONS.md, not
silently assumed secure. This endpoint IS the case a prior version of this
file's docstring warned about: it carries real (currently sandbox-realm,
ADR-0004) vendor business data -- price, inventory, reputation flags --
across the service boundary with no auth. This is a live, tracked
exposure (mitigated today only by ADR-0004's synthetic-only realm), not a
precedent to copy uncritically for a future endpoint that might carry real
(non-synthetic) vendor data."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.pagination import decode_cursor, encode_cursor
from packages.vendor.availability_model import effective_executable_status
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
    executable_status: str
    effective_executable_status: str
    has_positive_reputation: bool
    has_negative_reputation: bool


class InternalOfferListResponse(BaseModel):
    items: list[InternalOfferResponse]
    next_cursor: str | None = None


@router.get("/internal/offers", response_model=InternalOfferListResponse)
async def list_internal_offers(
    data_realm: str,
    as_of: datetime,
    cursor: str | None = None,
    limit: int = 100,
    conn: AsyncConnection = Depends(get_connection),
) -> InternalOfferListResponse:
    after_id = decode_cursor(cursor)[0] if cursor else 0
    rows = await list_offers_with_vendor_name_by_data_realm(conn, data_realm=data_realm, after_id=after_id, limit=limit)
    has_more = len(rows) > limit
    page = rows[:limit]
    next_cursor = encode_cursor((page[-1]["id"],)) if has_more else None
    reputation_cache: dict[int, tuple[bool, bool]] = {}
    items: list[InternalOfferResponse] = []
    as_of_iso = as_of.isoformat()
    for row in page:
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
                effective_executable_status=effective_executable_status(
                    row["executable_status"], has_negative_reputation=has_negative
                ),
                has_positive_reputation=has_positive,
                has_negative_reputation=has_negative,
            )
        )
    return InternalOfferListResponse(items=items, next_cursor=next_cursor)
