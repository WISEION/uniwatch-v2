"""Vendor-facing offers route (FR-VND-09 route-level tenant isolation
proof): GET /vendors/me/offers returns ONLY the calling vendor's own
offers. The vendor_id comes exclusively from the resolved identity
(get_current_vendor_id) -- it is never a path/query/body parameter here,
so there is no vendor_id value a caller could supply to reach another
vendor's data."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.vendor.vendor_store import list_offers_by_vendor

from ..deps import get_connection, get_current_vendor_id

router = APIRouter(prefix="/vendors", tags=["vendors"])


class OfferResponse(BaseModel):
    id: int
    vendor_id: int
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


class OfferListResponse(BaseModel):
    items: list[OfferResponse]


@router.get("/me/offers", response_model=OfferListResponse)
async def list_my_offers(
    conn: AsyncConnection = Depends(get_connection),
    vendor_id: int = Depends(get_current_vendor_id),
) -> OfferListResponse:
    rows = await list_offers_by_vendor(conn, vendor_id=vendor_id)
    return OfferListResponse(items=[OfferResponse(**row) for row in rows])
