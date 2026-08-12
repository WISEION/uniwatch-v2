"""Calibration-loop routes (Phase 4, task 4.D, TENDER_INTELLIGENCE_SPEC.md
Section7.4, P319): tender outcomes, loss post-mortems, and the
overhead-buffer read path. Every mutation here stores a fact a human already
knows (packages/decision/calibration_model.py) -- nothing is scored, weighted,
or derived (AGENTS.md hard ban #2).

An outcome may only be recorded for a tender we actually bid on
(_require_active_bid_decision, imported rather than duplicated from
execution_ledger.py) -- a tender we never bid on has no outcome for US, and
recording one would pollute win/loss statistics with tenders we never
entered. A loss reason may only be recorded on a `lost` outcome -- a "why we
lost" note on a won tender is a data-entry error, and storing it would
corrupt the rollup calibration_summary.py builds on top of this."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.decision.calibration_model import LossReason, TenderOutcome
from packages.decision.calibration_store import (
    list_loss_reasons_by_outcome,
    list_overhead_buffer_contributions,
    load_tender_outcome,
    store_loss_reason,
    store_tender_outcome,
)
from packages.platform.audit import write_audit_log
from packages.platform.errors import ApiError
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity

from ..deps import get_connection, get_current_identity
from .execution_ledger import _require_active_bid_decision

router = APIRouter(prefix="/tenders/{tender_id}", tags=["calibration"])


class OutcomeRequest(BaseModel):
    outcome: str
    our_submitted_amount: str | None = None
    winner_name: str | None = None
    winner_amount: str | None = None
    currency: str | None = None
    announced_at: str | None = None
    source_ref: str


class TenderOutcomeResponse(BaseModel):
    id: int
    tender_id: int
    outcome: str
    our_submitted_amount: str | None
    winner_name: str | None
    winner_amount: str | None
    currency: str | None
    announced_at: str | None
    source_ref: str
    entered_by: str
    entered_at: str


class LossReasonRequest(BaseModel):
    loss_reason: str
    note: str


class LossReasonResponse(BaseModel):
    id: int
    tender_outcome_id: int
    loss_reason: str
    note: str
    entered_by: str
    entered_at: str


class OverheadBufferContributionResponse(BaseModel):
    id: int
    tender_id: int
    deviation_category: str
    fact_count: int
    contributed_at: str


class OverheadBufferListResponse(BaseModel):
    items: list[OverheadBufferContributionResponse]


def _outcome_row_to_response(row: dict[str, Any]) -> TenderOutcomeResponse:
    return TenderOutcomeResponse(
        id=row["id"],
        tender_id=row["tender_id"],
        outcome=row["outcome"],
        our_submitted_amount=str(row["our_submitted_amount"]) if row["our_submitted_amount"] is not None else None,
        winner_name=row["winner_name"],
        winner_amount=str(row["winner_amount"]) if row["winner_amount"] is not None else None,
        currency=row["currency"],
        announced_at=row["announced_at"].isoformat() if row["announced_at"] is not None else None,
        source_ref=row["source_ref"],
        entered_by=row["entered_by"],
        entered_at=row["entered_at"].isoformat(),
    )


def _validated_outcome(payload: OutcomeRequest, *, tender_id: int, actor: str) -> TenderOutcome:
    """Route-boundary validation so a bad value is a clean 422, never a
    500 from the migration's CHECK constraint or from __post_init__
    escaping uncaught (4.C's sixth deferred item was exactly that defect
    on another route -- see docs/decisions/OPEN-QUESTIONS.md)."""
    try:
        return TenderOutcome(
            tender_id=tender_id,
            outcome=payload.outcome,
            our_submitted_amount=payload.our_submitted_amount,
            winner_name=payload.winner_name,
            winner_amount=payload.winner_amount,
            currency=payload.currency,
            announced_at=payload.announced_at,
            source_ref=payload.source_ref,
            entered_by=actor,
            entered_at=datetime.now(UTC).isoformat(),
        )
    except ValueError as exc:
        raise ApiError(status_code=422, code="invalid_outcome", message=str(exc)) from exc


@router.post("/outcome", response_model=TenderOutcomeResponse)
async def post_outcome(
    tender_id: int,
    payload: OutcomeRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.outcome.write", get_current_identity)),
) -> TenderOutcomeResponse:
    await _require_active_bid_decision(conn, tender_id=tender_id)

    existing = await load_tender_outcome(conn, tender_id=tender_id)
    if existing is not None:
        raise ApiError(
            status_code=409,
            code="outcome_already_recorded",
            message=f"tender {tender_id} already has a recorded outcome",
        )

    outcome = _validated_outcome(payload, tender_id=tender_id, actor=identity.subject)
    outcome_id = await store_tender_outcome(conn, outcome)
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="calibration.record_outcome",
        object_type="tender_outcome",
        object_id=str(outcome_id),
        object_version=None,
        reason=None,
    )

    loaded = await load_tender_outcome(conn, tender_id=tender_id)
    assert loaded is not None
    return _outcome_row_to_response(loaded)


@router.get("/outcome", response_model=TenderOutcomeResponse)
async def get_outcome(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.outcome.read", get_current_identity)),
) -> TenderOutcomeResponse:
    loaded = await load_tender_outcome(conn, tender_id=tender_id)
    if loaded is None:
        raise ApiError(
            status_code=404,
            code="outcome_not_found",
            message=f"tender {tender_id} has no recorded outcome",
        )
    return _outcome_row_to_response(loaded)


@router.post("/outcome/loss-reasons", response_model=LossReasonResponse)
async def post_loss_reason(
    tender_id: int,
    payload: LossReasonRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.outcome.write", get_current_identity)),
) -> LossReasonResponse:
    outcome_row = await load_tender_outcome(conn, tender_id=tender_id)
    if outcome_row is None:
        raise ApiError(
            status_code=404,
            code="outcome_not_found",
            message=f"tender {tender_id} has no recorded outcome",
        )
    if outcome_row["outcome"] != "lost":
        raise ApiError(
            status_code=409,
            code="outcome_not_a_loss",
            message=f"tender {tender_id}'s outcome is {outcome_row['outcome']!r}, not 'lost'",
        )

    try:
        reason = LossReason(
            loss_reason=payload.loss_reason,
            note=payload.note,
            entered_by=identity.subject,
            entered_at=datetime.now(UTC).isoformat(),
        )
    except ValueError as exc:
        raise ApiError(status_code=422, code="invalid_loss_reason", message=str(exc)) from exc

    reason_id = await store_loss_reason(conn, reason, tender_outcome_id=outcome_row["id"])
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="calibration.record_loss_reason",
        object_type="tender_loss_reason",
        object_id=str(reason_id),
        object_version=None,
        reason=None,
    )

    rows = await list_loss_reasons_by_outcome(conn, tender_outcome_id=outcome_row["id"])
    stored = next(r for r in rows if r["id"] == reason_id)
    return LossReasonResponse(
        id=stored["id"],
        tender_outcome_id=stored["tender_outcome_id"],
        loss_reason=stored["loss_reason"],
        note=stored["note"],
        entered_by=stored["entered_by"],
        entered_at=stored["entered_at"].isoformat(),
    )


@router.get("/overhead-buffer", response_model=OverheadBufferListResponse)
async def get_overhead_buffer(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.outcome.read", get_current_identity)),
) -> OverheadBufferListResponse:
    rows = await list_overhead_buffer_contributions(conn, tender_id=tender_id)
    return OverheadBufferListResponse(
        items=[
            OverheadBufferContributionResponse(
                id=r["id"],
                tender_id=r["tender_id"],
                deviation_category=r["deviation_category"],
                fact_count=r["fact_count"],
                contributed_at=r["contributed_at"].isoformat(),
            )
            for r in rows
        ]
    )
