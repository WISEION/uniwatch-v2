from __future__ import annotations

import httpx
from fastapi import Request

from packages.platform.app_factory import get_connection
from packages.platform.auth.session_store import resolve_session
from packages.platform.errors import ApiError
from packages.platform.ocr_engine import OcrEngine
from packages.platform.rbac.models import Identity

__all__ = ["SESSION_COOKIE_NAME", "get_connection", "get_current_identity", "get_ocr_engine", "get_vendor_http_client"]

SESSION_COOKIE_NAME = "uniwatch_session"


async def get_current_identity(request: Request) -> Identity:
    """Local-auth session resolution (Phase 6, task 6.A, D-IDP: lightweight
    local auth over users/roles/role_permissions, resolved 2026-08-14).
    Replaces the former dev-only `X-Dev-User` header entirely -- no
    dual-mode fallback. Deny-by-default: no cookie, an unknown/expired/
    revoked session, or a disabled user are all unauthenticated, never a
    default identity with any access."""
    token = request.cookies.get(SESSION_COOKIE_NAME)
    if token is None:
        raise ApiError(status_code=401, code="unauthenticated", message="session cookie required")

    engine = request.app.state.engine
    async with engine.connect() as conn:
        identity = await resolve_session(conn, token)
    if identity is None:
        raise ApiError(status_code=401, code="unauthenticated", message="invalid or expired session")
    return identity


async def get_vendor_http_client(request: Request) -> httpx.AsyncClient | None:
    """None in production (packages.contracts.vendor_api.list_vendor_offers
    opens and closes its own client per call, same as every other caller of
    that function) -- overridden in tests via
    app.dependency_overrides[get_vendor_http_client] to point at an
    in-process vendor app through httpx.ASGITransport, exactly like
    tests/contract/test_tender_vendor_contract.py already does for
    list_vendor_offers directly."""
    return getattr(request.app.state, "vendor_http_client", None)


async def get_ocr_engine(request: Request) -> OcrEngine | None:
    """None in production -- the route itself constructs the real
    OllamaOcrEngine from packages.platform.ocr_settings when this is None
    (same ocr_not_configured 503 discipline as before this dependency
    existed). Tests inject a fake OCR engine via `app.state.ocr_engine`,
    exactly the same override mechanism get_vendor_http_client above uses
    for the vendor http client, so the whole napkin-parse/reputation-feed
    code path can be driven end to end without a real Ollama instance."""
    return getattr(request.app.state, "ocr_engine", None)
