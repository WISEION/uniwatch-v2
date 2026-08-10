from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.decision.execution_napkin_provider import ExecutionNapkinParseError, ExecutionNapkinProvider
from packages.platform.ocr_engine import OcrEngine
from packages.tender.boq_line_model import BoqLine


class FakeOcrEngine(OcrEngine):
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        return self._response_text


def _line(source_line_id: int, description: str) -> BoqLine:
    return BoqLine(
        source_line_id=source_line_id,
        page_number=1,
        section=None,
        category_code=None,
        description=description,
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )


def _provider(response_payload: dict, *, boq_lines=None, lock_ins=None) -> ExecutionNapkinProvider:
    return ExecutionNapkinProvider(
        ocr_engine=FakeOcrEngine(json.dumps(response_payload)),
        image_bytes=b"fake-jpeg",
        mime_type="image/jpeg",
        evidence_id=1,
        tender_id=99,
        boq_lines=boq_lines or [],
        lock_ins=lock_ins or [],
    )


def test_generate_produces_one_fact_per_observation():
    payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 15,
                "deviation_reason": "used more rebar than planned",
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload, boq_lines=[_line(501, "Rebar 12mm, grade B500B")])
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")

    assert len(facts) == 1
    assert facts[0].tender_id == 99
    assert facts[0].boqline_source_line_id == 501
    assert facts[0].planned_qty == Decimal("10")  # from the matched BOQ line, never the photo
    assert facts[0].actual_qty == Decimal("15")
    assert facts[0].culprit_type == "internal"
    assert facts[0].evidence_source == "napkin-ocr:1"


def test_generate_resolves_vendor_culprit_to_a_vendor_id():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "crane did not arrive, half-day idle",
                "deviation_category": "downtime",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Acme Crane Co",
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload, lock_ins=[{"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"}])
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")

    assert facts[0].culprit_vendor_id == 42
    assert facts[0].culprit_vendor_name == "Acme Crane Co"
    assert facts[0].boqline_source_line_id is None
    assert facts[0].planned_qty is None


def test_generate_falls_back_to_the_supplied_date_when_observed_at_is_null():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "site was rained out",
                "deviation_category": "downtime",
                "culprit_type": "external",
                "culprit_vendor_name": None,
                "observed_at": None,
            }
        ]
    }
    provider = _provider(payload)
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")
    assert facts[0].observed_at == "2026-08-09T00:00:00+00:00"


def test_generate_handles_multiple_observations_in_one_capture():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "rework on formwork",
                "deviation_category": "rework",
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            },
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "site handover delayed by client",
                "deviation_category": "preliminaries",
                "culprit_type": "customer",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            },
        ]
    }
    provider = _provider(payload)
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")
    assert len(facts) == 2
    assert {f.culprit_type for f in facts} == {"internal", "customer"}


def test_generate_raises_on_invalid_json():
    provider = ExecutionNapkinProvider(
        ocr_engine=FakeOcrEngine("not json"),
        image_bytes=b"x",
        mime_type="image/jpeg",
        evidence_id=1,
        tender_id=99,
        boq_lines=[],
        lock_ins=[],
    )
    with pytest.raises(ExecutionNapkinParseError, match="not valid JSON"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_when_observations_key_is_missing():
    provider = _provider({"not_observations": []})
    with pytest.raises(ExecutionNapkinParseError, match="observations"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_when_deviation_reason_is_missing():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": None,
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="deviation_reason"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_on_unknown_culprit_type():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "something happened",
                "deviation_category": None,
                "culprit_type": "weather",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="culprit_type"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_on_non_numeric_actual_qty():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": "not-a-number",
                "deviation_reason": "used more rebar than planned",
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="actual_qty"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_when_vendor_culprit_has_no_name():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "late delivery",
                "deviation_category": None,
                "culprit_type": "vendor",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="culprit_vendor_name"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")
