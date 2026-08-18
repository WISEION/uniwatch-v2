"""Pilot feedback queue (Phase 6, task 6.D, master plan section18 Phase 6's
"training materials and feedback queue for pilot users" result). Any pilot
role can submit (see scripts/seed_pilot_users.py's platform.feedback.submit
grant across all 4 roles); only platform.feedback.triage (technical_specialist)
can list or resolve -- deny-by-default, same shape as admin_users.py."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.correlation import get_correlation_id
from packages.platform.errors import ApiError
from packages.platform.idempotency import IdempotencyKeyReused, IdempotencyStore, fingerprint
from packages.platform.pilot_feedback import (
    FeedbackNotFound,
    PilotFeedback,
    list_feedback,
    resolve_feedback,
    submit_feedback,
)
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity

from ..deps import get_connection, get_current_identity

router = APIRouter(prefix="/pilot-feedback", tags=["pilot-feedback"])

_idempotency_store = IdempotencyStore()

_CATEGORIES = ("bug", "question", "feature_request", "other")


class SubmitFeedbackRequest(BaseModel):
    category: str
    message: str


class ResolveFeedbackRequest(BaseModel):
    resolution_note: str


class FeedbackResponse(BaseModel):
    id: int
    submitted_by: str
    category: str
    message: str
    status: str
    resolution_note: str | None
    resolved_by: str | None
    submitted_at: str
    resolved_at: str | None


class FeedbackListResponse(BaseModel):
    items: list[FeedbackResponse]


def _to_response(feedback: PilotFeedback) -> FeedbackResponse:
    return FeedbackResponse(
        id=feedback.id,
        submitted_by=feedback.submitted_by,
        category=feedback.category,
        message=feedback.message,
        status=feedback.status,
        resolution_note=feedback.resolution_note,
        resolved_by=feedback.resolved_by,
        submitted_at=feedback.submitted_at.isoformat(),
        resolved_at=feedback.resolved_at.isoformat() if feedback.resolved_at else None,
    )


@router.post("", response_model=FeedbackResponse, status_code=201)
async def submit_feedback_route(
    body: SubmitFeedbackRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("platform.feedback.submit", get_current_identity)),
) -> FeedbackResponse:
    if body.category not in _CATEGORIES:
        raise ApiError(status_code=422, code="invalid_category", message=f"category must be one of {_CATEGORIES}")

    route = "POST /pilot-feedback"
    request_fingerprint = fingerprint(body.model_dump())
    try:
        existing = await _idempotency_store.reserve(conn, idempotency_key, route, request_fingerprint)
    except IdempotencyKeyReused as exc:
        raise ApiError(status_code=409, code="idempotency_key_reused", message=str(exc)) from exc
    if existing is not None:
        return FeedbackResponse(**existing.response_body)

    feedback = await submit_feedback(
        conn,
        submitted_by=identity.subject,
        category=body.category,
        message=body.message,
        correlation_id=get_correlation_id(),
    )
    response = _to_response(feedback)
    await _idempotency_store.store_response(conn, idempotency_key, route, 201, response.model_dump())
    return response


@router.get("", response_model=FeedbackListResponse)
async def list_feedback_route(
    status: str | None = None,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("platform.feedback.triage", get_current_identity)),
) -> FeedbackListResponse:
    items = await list_feedback(conn, status=status)
    return FeedbackListResponse(items=[_to_response(item) for item in items])


@router.post("/{feedback_id}/resolve", response_model=FeedbackResponse)
async def resolve_feedback_route(
    feedback_id: int,
    body: ResolveFeedbackRequest,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("platform.feedback.triage", get_current_identity)),
) -> FeedbackResponse:
    try:
        feedback = await resolve_feedback(
            conn,
            feedback_id=feedback_id,
            resolved_by=identity.subject,
            resolution_note=body.resolution_note,
        )
    except FeedbackNotFound as exc:
        raise ApiError(status_code=404, code="not_found", message=str(exc)) from exc
    return _to_response(feedback)
