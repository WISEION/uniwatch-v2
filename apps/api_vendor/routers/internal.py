"""Internal, service-to-service endpoints for the Vendor service (ADR-0006).
`GET /internal/ping` is deliberately trivial and unauthenticated -- it
proves the tender<->vendor real-API-contract mechanism (packages/contracts)
works end to end, without inventing real vendor business data
(packages/vendor has no domain code yet, synthetic-only pre-legal-gate).

Deliberately UNAUTHENTICATED: real service-to-service auth is deferred by
ADR-0006 to the still-open D-IDP/D-HOST decisions -- recorded as an open
gap in docs/decisions/OPEN-QUESTIONS.md, not silently assumed secure. Any
future /internal/* endpoint carrying real data must not copy this
unauthenticated pattern without first closing that gap."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["internal"])


class PingResponse(BaseModel):
    service: str
    status: str


@router.get("/internal/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(service="vendor", status="ok")
