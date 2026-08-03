"""Liveness/readiness (NFR-OBS-01, NFR-OBS-03). Readiness reads the
migration ledger and dependency connectivity — it never applies migrations
(FR-PLT-12 rule 1: schema never changes as a side effect of running code)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from packages.platform.errors import ApiError
from packages.platform.migrations_runner import MigrationRunner

router = APIRouter(tags=["health"])

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    schema_version: int
    expected_schema_version: int


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
        raise ApiError(
            status_code=503, code="not_ready", message=f"database unreachable: {exc}"
        ) from exc

    if current != settings.expected_schema_version:
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
