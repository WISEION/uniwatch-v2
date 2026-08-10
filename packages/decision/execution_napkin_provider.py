"""Real napkin-ingestion provider for the Execution Ledger (Phase 4, task
4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3, INV-18, P318) -- the
"photo of a completion act / voice note from site" half of napkin
ingestion, turning an OCR engine's extracted text into ExecutionFact
drafts. Same NapkinOcrProvider shape as packages/vendor/napkin_provider.py
but decision-domain: "planned" always comes from this codebase's own
already-stored BOQ line (execution_fact_resolution.py), never from the
photo/voice note -- a field-worker's guess at what was planned is not
authoritative.

EXECUTION_LEDGER_EXTRACTION_PROMPT and the JSON shape this parser expects
are THIS TASK'S OWN INVENTION, same honest limitation as
napkin_provider.py's NAPKIN_EXTRACTION_PROMPT: no source document supplies
a construction-site-deviation extraction schema, and no real captured
photo/voice note has been run through a real model in this session."""

from __future__ import annotations

import json
from decimal import Decimal, InvalidOperation
from typing import Any

from packages.platform.ocr_engine import OcrEngine
from packages.tender.boq_line_model import BoqLine

from .execution_fact_model import CULPRIT_TYPES, DEVIATION_CATEGORIES, ExecutionFact
from .execution_fact_resolution import resolve_boqline_reference, resolve_vendor_reference

EXECUTION_LEDGER_EXTRACTION_PROMPT = (
    "Extract every distinct execution deviation or observation from this "
    "document/note as JSON, exactly matching this shape, with no other "
    'text before or after the JSON: {"observations": [{"line_description": '
    'string | null, "actual_qty": number | null, "deviation_reason": '
    'string, "deviation_category": one of "preliminaries", "downtime", '
    '"rework", "last_mile", or null, "culprit_type": one of "vendor", '
    '"customer", "internal", "external", "culprit_vendor_name": string | '
    'null, "observed_at": ISO 8601 date string or null}]}. If a field is '
    "not stated in the image/note, use null -- never invent a value."
)


class ExecutionNapkinParseError(Exception):
    """The OCR engine's output isn't valid JSON, is missing the
    observations list, or an observation is missing a required field or
    names an unknown culprit_type/deviation_category -- always this one
    typed error, never a silently dropped observation."""


class ExecutionNapkinProvider:
    def __init__(
        self,
        *,
        ocr_engine: OcrEngine,
        image_bytes: bytes,
        mime_type: str,
        evidence_id: int,
        tender_id: int,
        boq_lines: list[BoqLine],
        lock_ins: list[dict[str, Any]],
    ) -> None:
        self._ocr_engine = ocr_engine
        self._image_bytes = image_bytes
        self._mime_type = mime_type
        self._evidence_id = evidence_id
        self._tender_id = tender_id
        self._boq_lines = boq_lines
        self._lock_ins = lock_ins

    def generate(self, *, observed_at_fallback: str) -> list[ExecutionFact]:
        raw_text = self._ocr_engine.parse_document(self._image_bytes, mime_type=self._mime_type)
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ExecutionNapkinParseError(f"OCR output is not valid JSON: {exc}") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
            raise ExecutionNapkinParseError(f"OCR output is missing an 'observations' list: {raw_text!r}")

        evidence_source = f"napkin-ocr:{self._evidence_id}"
        facts: list[ExecutionFact] = []
        for obs in payload["observations"]:
            if not isinstance(obs, dict):
                raise ExecutionNapkinParseError(f"observation is not an object: {obs!r}")

            deviation_reason = obs.get("deviation_reason")
            if not deviation_reason:
                raise ExecutionNapkinParseError(f"observation is missing a non-empty 'deviation_reason': {obs!r}")

            culprit_type = obs.get("culprit_type")
            if culprit_type not in CULPRIT_TYPES:
                raise ExecutionNapkinParseError(f"observation has unknown culprit_type: {culprit_type!r}")

            deviation_category = obs.get("deviation_category")
            if deviation_category is not None and deviation_category not in DEVIATION_CATEGORIES:
                raise ExecutionNapkinParseError(f"observation has unknown deviation_category: {deviation_category!r}")

            culprit_vendor_name = obs.get("culprit_vendor_name")
            if culprit_type == "vendor" and not culprit_vendor_name:
                raise ExecutionNapkinParseError("observation has culprit_type 'vendor' but no culprit_vendor_name")
            if culprit_type != "vendor":
                culprit_vendor_name = None

            matched_line = resolve_boqline_reference(self._boq_lines, obs.get("line_description"))
            culprit_vendor_id = (
                resolve_vendor_reference(self._lock_ins, culprit_vendor_name) if culprit_type == "vendor" else None
            )

            actual_qty_raw = obs.get("actual_qty")
            observed_at = obs.get("observed_at") or observed_at_fallback

            if actual_qty_raw is None:
                actual_qty = None
            else:
                try:
                    actual_qty = Decimal(str(actual_qty_raw))
                except (TypeError, ValueError, InvalidOperation) as exc:
                    raise ExecutionNapkinParseError(f"observation has a non-numeric 'actual_qty': {actual_qty_raw!r}") from exc

            facts.append(
                ExecutionFact(
                    tender_id=self._tender_id,
                    boqline_source_line_id=matched_line.source_line_id if matched_line else None,
                    planned_qty=matched_line.qty if matched_line else None,
                    actual_qty=actual_qty,
                    deviation_reason=str(deviation_reason),
                    deviation_category=deviation_category,
                    culprit_type=culprit_type,
                    culprit_vendor_name=culprit_vendor_name,
                    culprit_vendor_id=culprit_vendor_id,
                    evidence_source=evidence_source,
                    observed_at=observed_at,
                )
            )

        return facts
