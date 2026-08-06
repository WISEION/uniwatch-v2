"""FastAPI app factory for the Vendor service (ADR-0006: Tender and Vendor
are separate deployable processes, not routers on one app -- see
apps/api_tender/main.py for the other side). Same shape as
apps/api_tender/main.py: OpenAPI is the source of truth, strict validation,
unified error envelope, correlation id (FR-PLT-01, P117)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.platform.correlation import CorrelationIdMiddleware
from packages.platform.db import get_engine
from packages.platform.errors import install_error_handlers
from packages.platform.logging import configure_logging
from packages.platform.settings import Settings, get_settings

from .routers import health, internal, offers


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    # Engine created eagerly, not in lifespan (see apps/api_tender/main.py's
    # identical rationale: ASGITransport-based tests don't send lifespan
    # protocol events).
    engine = get_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(title="UNIWatch v2 API — Vendor", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(internal.router)
    app.include_router(offers.router)
    return app


app = create_app()
