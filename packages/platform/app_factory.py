"""Shared FastAPI app-bootstrap wiring for apps/api_tender and apps/api_vendor.

ADR-0006 makes Tender and Vendor two separate deployable processes, but the
generic startup sequence -- settings resolution, structured logging, engine
lifecycle, the correlation-id middleware, the unified error envelope, one
connection per request, and the liveness/readiness probes -- has no
service-specific content. It was previously hand-duplicated verbatim across
both apps/*/main.py, apps/*/deps.py, and apps/*/routers/health.py, which
drifts silently whenever one side gets tweaked and the other doesn't. This
module is the one place that sequence lives; each service's main.py still
calls build_app() once, from its own process's entry point -- ADR-0006's
"separate process" boundary is unchanged, only the duplicated code moves.
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import APIRouter, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from .correlation import CorrelationIdMiddleware
from .db import get_engine
from .errors import ApiError, install_error_handlers
from .logging import configure_logging
from .migrations_runner import MigrationRunner
from .settings import Settings, get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[2] / "migrations"


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    """One connection per request, wrapped in a transaction that commits if
    the route returns normally and rolls back on any exception -- this is
    what makes idempotency-reserve + mutation + idempotency-store atomic."""
    engine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    schema_version: int
    expected_schema_version: int


def build_health_router() -> APIRouter:
    """Liveness/readiness (NFR-OBS-01, NFR-OBS-03). Readiness reads the
    migration ledger and dependency connectivity -- it never applies
    migrations (FR-PLT-12 rule 1: schema never changes as a side effect of
    running code)."""
    router = APIRouter(tags=["health"])

    @router.get("/health/live", response_model=LivenessResponse)
    async def liveness() -> LivenessResponse:
        return LivenessResponse(status="ok")

    @router.get("/health/ready", response_model=ReadinessResponse)
    async def readiness(request: Request) -> ReadinessResponse:
        settings = request.app.state.settings
        runner = MigrationRunner(settings.asyncpg_dsn, MIGRATIONS_DIR)
        try:
            current = await runner.current_version()
        except Exception as exc:
            raise ApiError(status_code=503, code="not_ready", message=f"database unreachable: {exc}") from exc

        if current is None or current != settings.expected_schema_version:
            raise ApiError(
                status_code=503,
                code="not_ready",
                message="schema version mismatch",
                details=[{"expected": settings.expected_schema_version, "actual": current}],
            )
        return ReadinessResponse(
            status="ok",
            schema_version=current,
            expected_schema_version=settings.expected_schema_version,
        )

    return router


def build_app(*, title: str, routers: list[APIRouter], settings: Settings | None = None) -> FastAPI:
    """Common bootstrap for one apps/*/main.py::create_app(). Resolves
    settings, configures logging, creates the engine eagerly (connections
    are opened lazily by the pool, so this does not touch the network --
    kept out of `lifespan` so tests can drive the app through an ASGI
    transport that does not send lifespan protocol events), wires the
    correlation-id middleware and the unified error envelope, and includes
    the shared health router plus every service-specific router the caller
    passes."""
    settings = settings or get_settings()
    configure_logging()
    engine = get_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(title=title, lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(CorrelationIdMiddleware)
    # Added last so it wraps outermost (Starlette applies user_middleware
    # in reverse-registration order) -- CORS must see the OPTIONS preflight
    # and every response (including error responses) before anything else,
    # or the browser drops the response even when the server-side logic
    # behind it succeeded. Explicit origin allowlist only -- see
    # Settings.cors_allowed_origins for why "*" is never used here.
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(settings.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    install_error_handlers(app)
    app.include_router(build_health_router())
    for router in routers:
        app.include_router(router)
    return app
