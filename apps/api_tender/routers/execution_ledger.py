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
guessed."""

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
from packages.decision.execution_ledger_store import list_execution_facts_by_tender, store_execution_fact
from packages.decision.execution_napkin_evidence import save_execution_napkin_evidence
from packages.decision.execution_napkin_provider import ExecutionNapkinParseError, ExecutionNapkinProvider
from packages.decision.reputation_feed import map_to_reputation_event_type
from packages.platform.audit import write_audit_log
from packages.platform.errors import ApiError
from packages.platform.exception_queue import enqueue_exception
from packages.platform.ocr_engine import OcrEngineError
from packages.platform.ocr_settings import get_ocr_settings
from packages.platform.ollama_ocr_engine import OllamaOcrEngine
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity
from packages.tender.boq_lines_store import list_boq_lines_by_event
from packages.tender.normalized import get_event_id_for_tender

from ..deps import get_connection, get_current_identity, get_vendor_http_client

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


class ExecutionFactListResponse(BaseModel):
    items: list[dict[str, Any]]


@router.post("/execution-facts/napkin", response_model=NapkinSubmissionResponse, status_code=201)
async def submit_napkin_capture(
    tender_id: int,
    body: NapkinSubmissionRequest,
    request: Request,
    conn: AsyncConnection = Depends(get_connection),
    vendor_http_client: httpx.AsyncClient | None = Depends(get_vendor_http_client),
    identity: Identity = Depends(require_permission("decision.execution_facts.create", get_current_identity)),
) -> NapkinSubmissionResponse:
    raw_bytes = base64.b64decode(body.image_base64)
    correlation_id = f"execution-ledger-napkin-{tender_id}"
    evidence_id = await save_execution_napkin_evidence(
        conn,
        tender_id=tender_id,
        capture_kind=body.capture_kind,
        raw_bytes=raw_bytes,
        mime_type=body.mime_type,
        correlation_id=correlation_id,
    )

    if body.capture_kind == "voice":
        return NapkinSubmissionResponse(evidence_id=evidence_id, parsed=False, facts=[])

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
        await enqueue_exception(
            conn,
            source="execution-ledger",
            exception_type="napkin_unrecognized",
            category="needs_human",
            reason=str(exc),
            correlation_id=correlation_id,
            raw_ref=evidence_id,
            contract_name=None,
        )
        raise ApiError(status_code=422, code="napkin_unrecognized", message=str(exc)) from exc

    stored: list[ExecutionFact] = []
    for fact in drafts:
        await store_execution_fact(conn, fact)
        stored.append(fact)
        event_type = map_to_reputation_event_type(fact.deviation_category, fact.culprit_type)
        if event_type is not None and fact.culprit_vendor_id is not None:
            if body.reputation_ttl_days is None:
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
                    raw_ref=evidence_id,
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
                except VendorApiError:
                    await enqueue_exception(
                        conn,
                        source="execution-ledger",
                        exception_type="vendor_reputation_feed_failed",
                        category="needs_human",
                        reason=f"could not report reputation fact for vendor {fact.culprit_vendor_id}",
                        correlation_id=correlation_id,
                        raw_ref=evidence_id,
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
    return ExecutionFactListResponse(items=facts)
