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
from packages.tender.forecast_snapshot_store import (
    confirm_forecast_tender_link,
    earliest_observed_at,
    list_links_by_snapshot,
    load_forecast_card_snapshot,
    observed_lag_days,
    store_forecast_card_snapshot,
)
from packages.tender.signals_store import build_object_region_forecast_card

from ..deps import get_connection, get_current_identity
from .execution_ledger import _require_active_bid_decision

router = APIRouter(prefix="/tenders/{tender_id}", tags=["calibration"])

# build_object_region_forecast_card/confirm_forecast_tender_link span object
# regions and forecast snapshots, not one tender -- same reasoning as
# execution_ledger.py's organization_router (module docstring there): a
# second, separately-prefixed router carries them instead of `router`, which
# is prefixed /tenders/{tender_id}.
forecast_snapshot_router = APIRouter(tags=["calibration"])


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


class ForecastSnapshotRequest(BaseModel):
    object_region: str


class ForecastCardSnapshotResponse(BaseModel):
    id: int
    object_region: str
    is_composite: bool
    signal_types: list[str]
    budget_estimate: dict[str, Any] | None
    evidence_chain: list[dict[str, Any]]
    computed_at: str


class ForecastTenderLinkRequest(BaseModel):
    tender_id: int
    note: str


class ForecastTenderLinkResponse(BaseModel):
    id: int
    forecast_card_snapshot_id: int
    tender_id: int
    note: str
    confirmed_by: str
    confirmed_at: str
    # Named first_observed_at, never "publication date" -- it is the
    # earliest observed_at in the snapshot's own evidence chain, i.e. when
    # we (not the buyer) first saw a signal. See
    # forecast_snapshot_store.py's module docstring.
    observed_lag_days: int | None
    first_observed_at: str | None


class ForecastCardSnapshotDetailResponse(ForecastCardSnapshotResponse):
    links: list[ForecastTenderLinkResponse]


def _snapshot_row_to_response(row: dict[str, Any]) -> ForecastCardSnapshotResponse:
    return ForecastCardSnapshotResponse(
        id=row["id"],
        object_region=row["object_region"],
        is_composite=row["is_composite"],
        signal_types=row["signal_types"],
        budget_estimate=row["budget_estimate"],
        evidence_chain=row["evidence_chain"],
        computed_at=row["computed_at"].isoformat(),
    )


def _link_row_to_response(
    row: dict[str, Any], *, lag_days: int | None, first_observed_at: str | None
) -> ForecastTenderLinkResponse:
    return ForecastTenderLinkResponse(
        id=row["id"],
        forecast_card_snapshot_id=row["forecast_card_snapshot_id"],
        tender_id=row["tender_id"],
        note=row["note"],
        confirmed_by=row["confirmed_by"],
        confirmed_at=row["confirmed_at"].isoformat(),
        observed_lag_days=lag_days,
        first_observed_at=first_observed_at,
    )


@forecast_snapshot_router.post("/forecast-snapshots", response_model=ForecastCardSnapshotResponse)
async def post_forecast_snapshot(
    payload: ForecastSnapshotRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("tender.forecast_snapshot.write", get_current_identity)),
) -> ForecastCardSnapshotResponse:
    card = await build_object_region_forecast_card(conn, object_region=payload.object_region)
    if card is None:
        # Below the is_composite bar (forecast_card.py's honest stand-in for
        # P311's still-uncalibrated threshold, TBD-TIS-02) there is
        # genuinely no card to snapshot -- not an empty one.
        raise ApiError(
            status_code=409,
            code="no_forecast_card",
            message=f"object_region {payload.object_region!r} has no composite signal intersection",
        )

    snapshot_id = await store_forecast_card_snapshot(conn, card, computed_at=datetime.now(UTC).isoformat())
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="calibration.record_forecast_snapshot",
        object_type="forecast_card_snapshot",
        object_id=str(snapshot_id),
        object_version=None,
        reason=None,
    )

    loaded = await load_forecast_card_snapshot(conn, snapshot_id=snapshot_id)
    assert loaded is not None
    return _snapshot_row_to_response(loaded)


@forecast_snapshot_router.get("/forecast-snapshots/{snapshot_id}", response_model=ForecastCardSnapshotDetailResponse)
async def get_forecast_snapshot(
    snapshot_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("tender.forecast_snapshot.read", get_current_identity)),
) -> ForecastCardSnapshotDetailResponse:
    snapshot = await load_forecast_card_snapshot(conn, snapshot_id=snapshot_id)
    if snapshot is None:
        raise ApiError(
            status_code=404,
            code="forecast_snapshot_not_found",
            message=f"forecast snapshot {snapshot_id} not found",
        )

    first_observed_at = earliest_observed_at(snapshot["evidence_chain"])
    links = []
    for row in await list_links_by_snapshot(conn, snapshot_id=snapshot_id):
        lag_days = await observed_lag_days(conn, snapshot_id=snapshot_id, tender_id=row["tender_id"])
        links.append(_link_row_to_response(row, lag_days=lag_days, first_observed_at=first_observed_at))

    snapshot_response = _snapshot_row_to_response(snapshot)
    return ForecastCardSnapshotDetailResponse(**snapshot_response.model_dump(), links=links)


@forecast_snapshot_router.post("/forecast-snapshots/{snapshot_id}/tender-link", response_model=ForecastTenderLinkResponse)
async def post_forecast_tender_link(
    snapshot_id: int,
    payload: ForecastTenderLinkRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("tender.forecast_snapshot.write", get_current_identity)),
) -> ForecastTenderLinkResponse:
    snapshot = await load_forecast_card_snapshot(conn, snapshot_id=snapshot_id)
    if snapshot is None:
        raise ApiError(
            status_code=404,
            code="forecast_snapshot_not_found",
            message=f"forecast snapshot {snapshot_id} not found",
        )

    existing_links = await list_links_by_snapshot(conn, snapshot_id=snapshot_id)
    if any(link["tender_id"] == payload.tender_id for link in existing_links):
        # Checked here, not left to forecast_card_tender_links' UNIQUE
        # constraint -- a clean 409, not a 500 from IntegrityError (same
        # discipline as post_outcome's outcome_already_recorded check).
        raise ApiError(
            status_code=409,
            code="tender_link_already_confirmed",
            message=f"forecast snapshot {snapshot_id} is already linked to tender {payload.tender_id}",
        )

    link_id = await confirm_forecast_tender_link(
        conn,
        snapshot_id=snapshot_id,
        tender_id=payload.tender_id,
        note=payload.note,
        confirmed_by=identity.subject,
        confirmed_at=datetime.now(UTC).isoformat(),
    )
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="calibration.confirm_forecast_tender_link",
        object_type="forecast_card_tender_link",
        object_id=str(link_id),
        object_version=None,
        reason=None,
    )

    links = await list_links_by_snapshot(conn, snapshot_id=snapshot_id)
    stored = next(r for r in links if r["id"] == link_id)
    lag_days = await observed_lag_days(conn, snapshot_id=snapshot_id, tender_id=stored["tender_id"])
    first_observed_at = earliest_observed_at(snapshot["evidence_chain"])
    return _link_row_to_response(stored, lag_days=lag_days, first_observed_at=first_observed_at)
