"""FastAPI app factory: OpenAPI is the source of truth (every route has a
typed request/response model, so `/openapi.json` fully describes the
contract), strict validation, unified error envelope, correlation id
(FR-PLT-01, P117)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.platform.correlation import CorrelationIdMiddleware
from packages.platform.db import get_engine
from packages.platform.errors import install_error_handlers
from packages.platform.logging import configure_logging
from packages.platform.settings import Settings, get_settings

from .routers import admin_users, decision, health


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    # The engine is created eagerly (connections are opened lazily by the
    # pool, so this does not touch the network) rather than inside
    # `lifespan`, so tests can drive the app through an ASGI transport that
    # does not send lifespan protocol events.
    engine = get_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(title="UNIWatch v2 API", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    app.include_router(admin_users.router)
    app.include_router(decision.router)
    return app


app = create_app()
