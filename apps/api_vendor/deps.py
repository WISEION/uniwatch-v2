"""Vendor-side identity resolution for FR-VND-09 (route-level tenant
isolation). This is a Phase-3, sandbox-only credential mechanism (a
server-issued API key per synthetic vendor) -- deliberately NOT the
pilot's internal identity provider decision (D-IDP, Entra/OIDC for human
users, still open) and does not resolve it. Real vendor onboarding
(Phase 7, docs/reports/PLAN-MISSION-7.md) may replace this mechanism
entirely once that gate opens -- recorded in
docs/decisions/OPEN-QUESTIONS.md, not assumed permanent."""

from __future__ import annotations

from fastapi import Header, Request

from packages.platform.app_factory import get_connection
from packages.platform.errors import ApiError
from packages.vendor.vendor_store import get_vendor_id_by_api_key

__all__ = ["get_connection", "get_current_vendor_id"]


async def get_current_vendor_id(
    request: Request,
    x_vendor_api_key: str | None = Header(default=None),
) -> int:
    """Deny-by-default (INV-08, same discipline as
    apps/api_tender/deps.py::get_current_identity): a missing header or an
    unknown api_key are both unauthenticated, never a default vendor
    identity."""
    if x_vendor_api_key is None:
        raise ApiError(status_code=401, code="unauthenticated", message="X-Vendor-Api-Key header required")

    engine = request.app.state.engine
    async with engine.connect() as conn:
        vendor_id = await get_vendor_id_by_api_key(conn, api_key=x_vendor_api_key)
    if vendor_id is None:
        raise ApiError(status_code=401, code="unauthenticated", message="unknown api key")
    return vendor_id
