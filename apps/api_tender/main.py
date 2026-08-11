"""FastAPI app factory: OpenAPI is the source of truth (every route has a
typed request/response model, so `/openapi.json` fully describes the
contract), strict validation, unified error envelope, correlation id
(FR-PLT-01, P117). The generic bootstrap sequence lives in
packages/platform/app_factory.py, shared with apps/api_vendor/main.py."""

from __future__ import annotations

from fastapi import FastAPI

from packages.platform.app_factory import build_app
from packages.platform.settings import Settings

from .routers import admin_users, decision, execution_ledger


def create_app(settings: Settings | None = None) -> FastAPI:
    return build_app(
        title="UNIWatch v2 API",
        routers=[
            admin_users.router,
            decision.router,
            execution_ledger.router,
            execution_ledger.organization_router,
        ],
        settings=settings,
    )


app = create_app()
