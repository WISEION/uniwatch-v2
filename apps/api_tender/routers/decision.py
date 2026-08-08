"""Decision Core (Phase 4, task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1):
Go/No-Go and Bid/No-Bid/Conditional Bid. Human authority is final and
exclusive (ADR-0005) -- this router never computes or phrases a verdict
itself, only the one real derived signal (packages/decision/bid_readiness.py)
and structured storage for human-entered qualitative inputs and the
human's own decision.

GET /bid-readiness-candidate is the first place in this codebase that
calls match_boq_line/summarize_boq_matches against a real persisted
tender's BOQ lines and a real (paginated) vendor-offer fetch -- task 3.D's
final review flagged this end-to-end wiring as a real, deferred gap; this
router closes it.

data_realm is hardcoded to "vendor-sandbox" -- the only realm with any
data today (ADR-0004, synthetic-only until a legal gate). Revisit once
vendor-production data exists (docs/decisions/OPEN-QUESTIONS.md)."""

from __future__ import annotations

from datetime import UTC, datetime

import httpx
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.contracts.vendor_api import VendorApiError, list_vendor_offers
from packages.decision.bid_readiness import build_bid_readiness_candidate
from packages.decision.decision_model import DECISION_TYPES, Decision, GoNoGoInputs
from packages.decision.decision_store import (
    load_bid_readiness_candidate,
    store_bid_readiness_candidate,
    store_decision,
    store_go_no_go_inputs,
    store_lock_in_requirement,
)
from packages.platform.audit import write_audit_log
from packages.platform.errors import ApiError
from packages.platform.idempotency import IdempotencyKeyReused, IdempotencyStore, fingerprint
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity
from packages.tender.boq_lines_store import list_boq_lines_by_tender_version
from packages.tender.normalized import get_current_tender_version_id

from ..deps import get_connection, get_current_identity, get_vendor_http_client

router = APIRouter(prefix="/tenders/{tender_id}", tags=["decision"])

_idempotency_store = IdempotencyStore()


class GoNoGoInputsRequest(BaseModel):
    company_profile_notes: str
    qualification_notes: str
    financing_notes: str
    customer_reputation_notes: str
    pre_designated_winner_suspected: bool


class GoNoGoInputsResponse(BaseModel):
    id: int
    tender_id: int
    company_profile_notes: str
    qualification_notes: str
    financing_notes: str
    customer_reputation_notes: str
    pre_designated_winner_suspected: bool
    entered_by: str
    entered_at: datetime


class CriticalLineResponse(BaseModel):
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str


class BidReadinessCandidateResponse(BaseModel):
    id: int
    tender_id: int
    green_amount: str
    yellow_amount: str
    red_amount: str
    unpriced_line_count: int
    non_matchable_line_count: int
    non_matchable_amount: str
    total_priced_amount: str
    green_pct: float
    yellow_pct: float
    red_pct: float
    is_lottery: bool
    critical_lines: list[CriticalLineResponse]
    computed_at: datetime


class DecisionRequest(BaseModel):
    decision_type: str
    conditions: list[str]
    deadline: datetime | None = None
    justification: str
    go_no_go_inputs_id: int | None = None
    bid_readiness_candidate_id: int | None = None


class LockInRequirementResponse(BaseModel):
    id: int
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str
    status: str


class DecisionResponse(BaseModel):
    id: int
    tender_id: int
    decision_type: str
    conditions: list[str]
    deadline: datetime | None
    justification: str
    actor: str
    decided_at: datetime
    lock_in_requirements: list[LockInRequirementResponse]


@router.post("/go-no-go-inputs", response_model=GoNoGoInputsResponse, status_code=201)
async def create_go_no_go_inputs(
    tender_id: int,
    body: GoNoGoInputsRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.go_no_go.create", get_current_identity)),
) -> GoNoGoInputsResponse:
    route = "POST /tenders/{tender_id}/go-no-go-inputs"
    request_fingerprint = fingerprint({"tender_id": tender_id, **body.model_dump()})
    try:
        existing = await _idempotency_store.reserve(conn, idempotency_key, route, request_fingerprint)
    except IdempotencyKeyReused as exc:
        raise ApiError(status_code=409, code="idempotency_key_reused", message=str(exc)) from exc
    if existing is not None:
        return GoNoGoInputsResponse(**existing.response_body)

    entered_at = datetime.now(UTC).isoformat()
    inputs = GoNoGoInputs(
        tender_id=tender_id,
        company_profile_notes=body.company_profile_notes,
        qualification_notes=body.qualification_notes,
        financing_notes=body.financing_notes,
        customer_reputation_notes=body.customer_reputation_notes,
        pre_designated_winner_suspected=body.pre_designated_winner_suspected,
        entered_by=identity.subject,
        entered_at=entered_at,
    )
    try:
        inputs_id = await store_go_no_go_inputs(conn, inputs)
    except IntegrityError as exc:
        raise ApiError(status_code=422, code="invalid_reference", message=f"tender {tender_id} does not exist") from exc
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="go_no_go_inputs.create",
        object_type="go_no_go_inputs",
        object_id=str(inputs_id),
        object_version=None,
        reason=None,
    )
    response = GoNoGoInputsResponse(
        id=inputs_id,
        tender_id=tender_id,
        company_profile_notes=inputs.company_profile_notes,
        qualification_notes=inputs.qualification_notes,
        financing_notes=inputs.financing_notes,
        customer_reputation_notes=inputs.customer_reputation_notes,
        pre_designated_winner_suspected=inputs.pre_designated_winner_suspected,
        entered_by=inputs.entered_by,
        entered_at=datetime.fromisoformat(inputs.entered_at),
    )
    await _idempotency_store.store_response(conn, idempotency_key, route, 201, response.model_dump(mode="json"))
    return response


@router.get("/bid-readiness-candidate", response_model=BidReadinessCandidateResponse)
async def get_bid_readiness_candidate(
    tender_id: int,
    as_of: datetime,
    request: Request,
    conn: AsyncConnection = Depends(get_connection),
    vendor_http_client: httpx.AsyncClient | None = Depends(get_vendor_http_client),
    identity: Identity = Depends(require_permission("decision.bid_readiness.read", get_current_identity)),
) -> BidReadinessCandidateResponse:
    if as_of.tzinfo is None:
        raise ApiError(status_code=422, code="naive_datetime", message="as_of must include a timezone offset")

    tender_version_id = await get_current_tender_version_id(conn, tender_id=tender_id)
    if tender_version_id is None:
        raise ApiError(status_code=404, code="not_found", message=f"tender {tender_id} not found or has no version")

    boq_lines = await list_boq_lines_by_tender_version(conn, tender_version_id=tender_version_id)
    if not boq_lines:
        raise ApiError(status_code=404, code="not_found", message=f"tender {tender_id} has no BOQ lines")

    settings = request.app.state.settings
    try:
        offers = await list_vendor_offers(
            settings.vendor_service_base_url,
            data_realm="vendor-sandbox",
            as_of=as_of.isoformat(),
            client=vendor_http_client,
        )
    except VendorApiError as exc:
        raise ApiError(status_code=502, code="vendor_service_unavailable", message=str(exc)) from exc

    candidate = build_bid_readiness_candidate(
        tender_id, boq_lines, offers, as_of=as_of, computed_at=datetime.now(UTC).isoformat()
    )
    candidate_id = await store_bid_readiness_candidate(conn, candidate)
    return BidReadinessCandidateResponse(
        id=candidate_id,
        tender_id=candidate.tender_id,
        green_amount=str(candidate.summary.green_amount),
        yellow_amount=str(candidate.summary.yellow_amount),
        red_amount=str(candidate.summary.red_amount),
        unpriced_line_count=candidate.summary.unpriced_line_count,
        non_matchable_line_count=candidate.summary.non_matchable_line_count,
        non_matchable_amount=str(candidate.summary.non_matchable_amount),
        total_priced_amount=str(candidate.summary.total_priced_amount),
        green_pct=candidate.summary.green_pct,
        yellow_pct=candidate.summary.yellow_pct,
        red_pct=candidate.summary.red_pct,
        is_lottery=candidate.is_lottery,
        critical_lines=[CriticalLineResponse(**cl.__dict__) for cl in candidate.critical_lines],
        computed_at=datetime.fromisoformat(candidate.computed_at),
    )


@router.post("/decisions", response_model=DecisionResponse, status_code=201)
async def create_decision(
    tender_id: int,
    body: DecisionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.decisions.create", get_current_identity)),
) -> DecisionResponse:
    if body.decision_type not in DECISION_TYPES:
        raise ApiError(status_code=422, code="unknown_decision_type", message=f"unknown decision_type: {body.decision_type}")

    route = "POST /tenders/{tender_id}/decisions"
    request_fingerprint = fingerprint({"tender_id": tender_id, **body.model_dump(mode="json")})
    try:
        existing = await _idempotency_store.reserve(conn, idempotency_key, route, request_fingerprint)
    except IdempotencyKeyReused as exc:
        raise ApiError(status_code=409, code="idempotency_key_reused", message=str(exc)) from exc
    if existing is not None:
        return DecisionResponse(**existing.response_body)

    decided_at = datetime.now(UTC).isoformat()
    decision = Decision(
        tender_id=tender_id,
        decision_type=body.decision_type,
        conditions=tuple(body.conditions),
        deadline=body.deadline.isoformat() if body.deadline else None,
        justification=body.justification,
        actor=identity.subject,
        decided_at=decided_at,
        go_no_go_inputs_id=body.go_no_go_inputs_id,
        bid_readiness_candidate_id=body.bid_readiness_candidate_id,
    )
    try:
        decision_id = await store_decision(conn, decision)
    except IntegrityError as exc:
        raise ApiError(
            status_code=422,
            code="invalid_reference",
            message=(
                f"tender {tender_id}, go_no_go_inputs_id {body.go_no_go_inputs_id}, "
                f"or bid_readiness_candidate_id {body.bid_readiness_candidate_id} does not exist"
            ),
        ) from exc
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="decision.create",
        object_type="decision",
        object_id=str(decision_id),
        object_version=None,
        reason=decision.justification,
    )

    lock_ins: list[LockInRequirementResponse] = []
    if body.decision_type in ("bid", "conditional_bid") and body.bid_readiness_candidate_id is not None:
        try:
            candidate_row = await load_bid_readiness_candidate(conn, body.bid_readiness_candidate_id)
        except ValueError as exc:
            raise ApiError(status_code=422, code="invalid_reference", message=str(exc)) from exc
        for line in candidate_row["critical_lines"]:
            lock_in_id = await store_lock_in_requirement(
                conn,
                tender_id=tender_id,
                decision_id=decision_id,
                boqline_source_line_id=line["boqline_source_line_id"],
                vendor_id=line["vendor_id"],
                vendor_name=line["vendor_name"],
            )
            lock_ins.append(
                LockInRequirementResponse(
                    id=lock_in_id,
                    boqline_source_line_id=line["boqline_source_line_id"],
                    vendor_id=line["vendor_id"],
                    vendor_name=line["vendor_name"],
                    status="pending",
                )
            )

    response = DecisionResponse(
        id=decision_id,
        tender_id=tender_id,
        decision_type=decision.decision_type,
        conditions=list(decision.conditions),
        deadline=datetime.fromisoformat(decision.deadline) if decision.deadline else None,
        justification=decision.justification,
        actor=decision.actor,
        decided_at=datetime.fromisoformat(decision.decided_at),
        lock_in_requirements=lock_ins,
    )
    await _idempotency_store.store_response(conn, idempotency_key, route, 201, response.model_dump(mode="json"))
    return response
