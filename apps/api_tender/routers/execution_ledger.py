"""Execution Ledger routes (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md
Section7.3, P318). Evidence is always saved first, before any parse attempt
(INV-18: capture must never depend on whether the system currently
understands it). A 'voice' capture is stored but not parsed -- ASR is
still an open tech-choice gap (docs/decisions/OPEN-QUESTIONS.md), same as
packages/vendor's napkin ingestion. OCR config comes from
packages/platform/ocr_settings.py; an unconfigured OCR backend is a real,
loud 503, never a silent no-op (AGENTS.md hard ban #3).

reputation_ttl_days has NO default beyond None (INV-17, TBD-TIS-01): a
vendor-culprit fact with a mappable reputation event_type is only ever
reported to the Vendor service when the caller explicitly supplies a TTL;
otherwise the gap is queued for a human via exception_queue, never
guessed.

Durability note (task 4.C review fix): `Depends(get_connection)` wraps this
whole request in ONE transaction that rolls back on any exception raised
from the route -- including the `ApiError`s this route itself raises for
`ocr_not_configured`/`napkin_unrecognized`. Evidence capture (INV-18) and
the napkin_unrecognized exception-queue record must survive those rollbacks,
so both are written through their own, separately-committed
`request.app.state.engine.begin()` scope rather than the route's shared
`conn` -- everything else (storing ExecutionFacts, the reputation feed,
the audit log) legitimately IS meant to be atomic with the rest of a
successful request, and keeps using the shared `conn`."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.contracts.vendor_api import VendorApiError, report_reputation_fact
from packages.decision.decision_store import list_lock_in_requirements_by_tender
from packages.decision.execution_fact_model import ExecutionFact
from packages.decision.execution_ledger_store import (
    list_execution_facts_by_organization_voen,
    list_execution_facts_by_tender,
    store_execution_fact,
    store_overhead_buffer_contribution,
)
from packages.decision.execution_ledger_summary import summarize_deviation_category_counts, summarize_plan_fact_deltas
from packages.decision.execution_napkin_evidence import save_execution_napkin_evidence
from packages.decision.execution_napkin_provider import ExecutionNapkinParseError, ExecutionNapkinProvider
from packages.decision.reputation_feed import map_to_reputation_event_type
from packages.platform.audit import write_audit_log
from packages.platform.errors import ApiError
from packages.platform.exception_queue import enqueue_exception
from packages.platform.ocr_engine import OcrEngine, OcrEngineError
from packages.platform.ocr_settings import get_ocr_settings
from packages.platform.ollama_ocr_engine import OllamaOcrEngine
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity
from packages.tender.boq_lines_store import list_boq_lines_by_event
from packages.tender.normalized import get_event_id_for_tender

from ..deps import get_connection, get_current_identity, get_ocr_engine, get_vendor_http_client

router = APIRouter(prefix="/tenders/{tender_id}", tags=["execution-ledger"])


class NapkinSubmissionRequest(BaseModel):
    capture_kind: str
    mime_type: str
    image_base64: str
    # No default: INV-17 explicitly leaves exact TTL numbers for the
    # qualification/reputation fact class as unresolved (TBD-TIS-01) --
    # this codebase's own synthetic_reputation.py only ever samples an
    # arbitrary TTL for SYNTHETIC demo data, never for a fact stemming from
    # a real observation. A vendor-culprit fact with a mappable event_type
    # is therefore only reported to the Vendor service when the caller
    # supplies this explicitly; otherwise it is queued for a human to
    # decide (see below), never silently defaulted.
    reputation_ttl_days: int | None = None


class ExecutionFactResponse(BaseModel):
    boqline_source_line_id: int | None
    planned_qty: str | None
    actual_qty: str | None
    deviation_reason: str
    deviation_category: str | None
    culprit_type: str
    culprit_vendor_name: str | None
    culprit_vendor_id: int | None
    evidence_source: str
    observed_at: str


class NapkinSubmissionResponse(BaseModel):
    evidence_id: int
    parsed: bool
    facts: list[ExecutionFactResponse]


class ExecutionFactRecordResponse(BaseModel):
    """GET's own typed shape (distinct from ExecutionFactResponse only in
    carrying `id`/`tender_id`, which a stored-record listing should
    identify and the POST response doesn't need). planned_qty/actual_qty
    are stringified the same way POST's response already does --
    FastAPI's jsonable_encoder silently narrows Decimal to float otherwise,
    which is exactly the loss of precision this task's own POST response
    was already written to avoid."""

    id: int
    tender_id: int
    boqline_source_line_id: int | None
    planned_qty: str | None
    actual_qty: str | None
    deviation_reason: str
    deviation_category: str | None
    culprit_type: str
    culprit_vendor_name: str | None
    culprit_vendor_id: int | None
    evidence_source: str
    observed_at: str


class ExecutionFactListResponse(BaseModel):
    items: list[ExecutionFactRecordResponse]


@router.post("/execution-facts/napkin", response_model=NapkinSubmissionResponse, status_code=201)
async def submit_napkin_capture(
    tender_id: int,
    body: NapkinSubmissionRequest,
    request: Request,
    conn: AsyncConnection = Depends(get_connection),
    vendor_http_client: httpx.AsyncClient | None = Depends(get_vendor_http_client),
    ocr_engine_override: OcrEngine | None = Depends(get_ocr_engine),
    identity: Identity = Depends(require_permission("decision.execution_facts.create", get_current_identity)),
) -> NapkinSubmissionResponse:
    raw_bytes = base64.b64decode(body.image_base64)
    correlation_id = f"execution-ledger-napkin-{tender_id}"

    # INV-18: evidence capture must never depend on whether the rest of
    # this request succeeds. `conn` (Depends(get_connection)) rolls back
    # on any exception raised further down this function -- so this write
    # gets its own transaction, committed immediately, independent of that.
    async with request.app.state.engine.begin() as evidence_conn:
        evidence_id = await save_execution_napkin_evidence(
            evidence_conn,
            tender_id=tender_id,
            capture_kind=body.capture_kind,
            raw_bytes=raw_bytes,
            mime_type=body.mime_type,
            correlation_id=correlation_id,
        )

    if body.capture_kind == "voice":
        await write_audit_log(
            conn,
            actor=identity.subject,
            action="execution_facts.create",
            object_type="execution_napkin_evidence",
            object_id=str(evidence_id),
            object_version=None,
            reason=None,
        )
        return NapkinSubmissionResponse(evidence_id=evidence_id, parsed=False, facts=[])

    if ocr_engine_override is not None:
        # Test-only injection point (mirrors get_vendor_http_client) -- lets
        # a fake OCR engine drive this route's parse/resolution/reputation
        # code paths without a real Ollama instance.
        ocr_engine: OcrEngine = ocr_engine_override
    else:
        settings = get_ocr_settings()
        if not settings.ocr_model_name:
            raise ApiError(status_code=503, code="ocr_not_configured", message="OCR_MODEL_NAME is not set")
        ocr_engine = OllamaOcrEngine(base_url=settings.ollama_base_url, model_name=settings.ocr_model_name)

    event_id = await get_event_id_for_tender(conn, tender_id=tender_id)
    boq_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id) if event_id is not None else []
    lock_ins = await list_lock_in_requirements_by_tender(conn, tender_id=tender_id)

    provider = ExecutionNapkinProvider(
        ocr_engine=ocr_engine,
        image_bytes=raw_bytes,
        mime_type=body.mime_type,
        evidence_id=evidence_id,
        tender_id=tender_id,
        boq_lines=boq_lines,
        lock_ins=lock_ins,
    )
    observed_at_fallback = datetime.now(UTC).isoformat()
    try:
        drafts = provider.generate(observed_at_fallback=observed_at_fallback)
    except (ExecutionNapkinParseError, OcrEngineError) as exc:
        # Same durability concern as the evidence save above: this record
        # must survive the ApiError raised right below, which rolls back
        # the route's shared `conn`. raw_ref is deliberately None -- that
        # column is a real FK to raw_snapshots (id), a different table
        # than execution_napkin_evidence, and there is no schema support
        # for a real FK to the latter; correlation_id is how a human finds
        # the right evidence row instead of a wrong/mismatched raw_ref.
        async with request.app.state.engine.begin() as exc_conn:
            await enqueue_exception(
                exc_conn,
                source="execution-ledger",
                exception_type="napkin_unrecognized",
                category="needs_human",
                reason=str(exc),
                correlation_id=correlation_id,
                raw_ref=None,
                contract_name=None,
            )
        raise ApiError(status_code=422, code="napkin_unrecognized", message=str(exc)) from exc

    stored: list[ExecutionFact] = []
    for fact in drafts:
        await store_execution_fact(conn, fact)
        stored.append(fact)
        event_type = map_to_reputation_event_type(fact.deviation_category, fact.culprit_type)
        if event_type is not None:
            if fact.culprit_vendor_id is None:
                # The OCR-reported vendor name didn't resolve against any
                # of this tender's lock-in requirements -- surface the gap
                # rather than silently dropping a reputation-worthy event.
                await enqueue_exception(
                    conn,
                    source="execution-ledger",
                    exception_type="vendor_reputation_unresolved_vendor",
                    category="needs_human",
                    reason=(
                        f"vendor culprit {fact.culprit_vendor_name!r} on tender {tender_id} did not resolve to "
                        f"any lock-in requirement's vendor_id; reputation event ({event_type}) not reported"
                    ),
                    correlation_id=correlation_id,
                    raw_ref=None,
                    contract_name=None,
                )
            elif body.reputation_ttl_days is None:
                # TBD-TIS-01 (INV-17): no approved TTL number exists for a
                # real reputation/qualification-class fact -- surface the
                # gap rather than guess one, hard ban #3.
                await enqueue_exception(
                    conn,
                    source="execution-ledger",
                    exception_type="vendor_reputation_ttl_missing",
                    category="needs_human",
                    reason=(
                        f"vendor {fact.culprit_vendor_id} reputation fact ({event_type}) ready but "
                        "reputation_ttl_days was not supplied (TBD-TIS-01)"
                    ),
                    correlation_id=correlation_id,
                    raw_ref=None,
                    contract_name=None,
                )
            else:
                try:
                    await report_reputation_fact(
                        request.app.state.settings.vendor_service_base_url,
                        vendor_id=fact.culprit_vendor_id,
                        event_type=event_type,
                        project_ref=str(tender_id),
                        source_ref=fact.evidence_source,
                        observed_at=fact.observed_at,
                        ttl_days=body.reputation_ttl_days,
                        client=vendor_http_client,
                    )
                except VendorApiError as exc:
                    await enqueue_exception(
                        conn,
                        source="execution-ledger",
                        exception_type="vendor_reputation_feed_failed",
                        category="needs_human",
                        reason=f"could not report reputation fact for vendor {fact.culprit_vendor_id}: {exc}",
                        correlation_id=correlation_id,
                        raw_ref=None,
                        contract_name=None,
                    )

    await write_audit_log(
        conn,
        actor=identity.subject,
        action="execution_facts.create",
        object_type="execution_napkin_evidence",
        object_id=str(evidence_id),
        object_version=None,
        reason=None,
    )

    return NapkinSubmissionResponse(
        evidence_id=evidence_id,
        parsed=True,
        facts=[
            ExecutionFactResponse(
                boqline_source_line_id=f.boqline_source_line_id,
                planned_qty=str(f.planned_qty) if f.planned_qty is not None else None,
                actual_qty=str(f.actual_qty) if f.actual_qty is not None else None,
                deviation_reason=f.deviation_reason,
                deviation_category=f.deviation_category,
                culprit_type=f.culprit_type,
                culprit_vendor_name=f.culprit_vendor_name,
                culprit_vendor_id=f.culprit_vendor_id,
                evidence_source=f.evidence_source,
                observed_at=f.observed_at,
            )
            for f in stored
        ],
    )


@router.get("/execution-facts", response_model=ExecutionFactListResponse)
async def get_execution_facts(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.read", get_current_identity)),
) -> ExecutionFactListResponse:
    facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)
    return ExecutionFactListResponse(
        items=[
            ExecutionFactRecordResponse(
                id=f["id"],
                tender_id=f["tender_id"],
                boqline_source_line_id=f["boqline_source_line_id"],
                planned_qty=str(f["planned_qty"]) if f["planned_qty"] is not None else None,
                actual_qty=str(f["actual_qty"]) if f["actual_qty"] is not None else None,
                deviation_reason=f["deviation_reason"],
                deviation_category=f["deviation_category"],
                culprit_type=f["culprit_type"],
                culprit_vendor_name=f["culprit_vendor_name"],
                culprit_vendor_id=f["culprit_vendor_id"],
                evidence_source=f["evidence_source"],
                observed_at=f["observed_at"].isoformat(),
            )
            for f in facts
        ]
    )


class PlanFactDeltaResponse(BaseModel):
    boqline_source_line_id: int
    planned_qty: str
    actual_qty: str
    delta: str


class ExecutionSummaryResponse(BaseModel):
    plan_fact_deltas: list[PlanFactDeltaResponse]
    deviation_category_counts: dict[str, int]


async def _build_summary(conn: AsyncConnection, *, tender_id: int) -> ExecutionSummaryResponse:
    facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)
    deltas = summarize_plan_fact_deltas(facts)
    counts = summarize_deviation_category_counts(facts)
    return ExecutionSummaryResponse(
        plan_fact_deltas=[
            PlanFactDeltaResponse(
                boqline_source_line_id=d.boqline_source_line_id,
                planned_qty=str(d.planned_qty),
                actual_qty=str(d.actual_qty),
                delta=str(d.delta),
            )
            for d in deltas
        ],
        deviation_category_counts=counts,
    )


@router.get("/execution-summary", response_model=ExecutionSummaryResponse)
async def get_execution_summary(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.read", get_current_identity)),
) -> ExecutionSummaryResponse:
    return await _build_summary(conn, tender_id=tender_id)


@router.post("/close-project", response_model=ExecutionSummaryResponse)
async def close_project(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.close_project", get_current_identity)),
) -> ExecutionSummaryResponse:
    summary = await _build_summary(conn, tender_id=tender_id)
    contributed_at = datetime.now(UTC).isoformat()
    for category, count in summary.deviation_category_counts.items():
        await store_overhead_buffer_contribution(
            conn, tender_id=tender_id, deviation_category=category, fact_count=count, contributed_at=contributed_at
        )
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="execution_ledger.close_project",
        object_type="tender",
        object_id=str(tender_id),
        object_version=None,
        reason=None,
    )
    return summary


class OrganizationExecutionHistoryResponse(BaseModel):
    items: list[dict[str, Any]]


# get_organization_execution_history spans tenders (it looks up every
# tender sharing one buyer's organization_voen) -- it does not belong on
# `router`, which is prefixed /tenders/{tender_id}. A second, separate
# router carries it instead.
organization_router = APIRouter(prefix="/organizations/{organization_voen}", tags=["execution-ledger"])


@organization_router.get("/execution-history", response_model=OrganizationExecutionHistoryResponse)
async def get_organization_execution_history(
    organization_voen: str,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.read", get_current_identity)),
) -> OrganizationExecutionHistoryResponse:
    items = await list_execution_facts_by_organization_voen(conn, organization_voen=organization_voen)
    return OrganizationExecutionHistoryResponse(items=items)
