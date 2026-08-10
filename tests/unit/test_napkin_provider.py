"""Unit tests for packages/vendor/napkin_provider.py. A fake OcrEngine
stands in for the real Ollama-backed one -- proves the parsing/atom
mechanism on a canned OCR output, independent of whether a real model is
reachable (same discipline as bom_lines_job.py's `fetch_page` injection:
the mechanism is proven with a fake, the real HTTP wiring is proven
separately in test_ollama_ocr_engine.py)."""

from __future__ import annotations

import json

import pytest

from packages.vendor.napkin_provider import NapkinOcrProvider, NapkinParseError
from packages.platform.ocr_engine import OcrEngine

AS_OF = "2026-08-08T00:00:00+00:00"

_VALID_ITEM = {
    "material": "cement M400",
    "price": 120.0,
    "currency": "AZN",
    "vat_rate": 18.0,
    "uom": "t",
    "uom_canonical_qty": 1.0,
    "moq": 5.0,
    "capacity": 100.0,
    "inventory": 40.0,
    "valid_from": "2026-08-01T00:00:00+00:00",
    "valid_until": "2026-09-01T00:00:00+00:00",
}


class _FakeOcrEngine:
    def __init__(self, text: str) -> None:
        self._text = text

    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        return self._text


def _provider(text: str, *, data_realm: str = "vendor-sandbox", watermark: str = "SYNTHETIC") -> NapkinOcrProvider:
    engine: OcrEngine = _FakeOcrEngine(text)
    return NapkinOcrProvider(
        ocr_engine=engine,
        image_bytes=b"fake-photo-bytes",
        mime_type="image/jpeg",
        evidence_id=42,
        data_realm=data_realm,
        watermark=watermark,
    )


def test_generate_parses_a_well_formed_ocr_json_response():
    payload = {"vendor_name": "Rəşid Materials", "items": [_VALID_ITEM]}
    provider = _provider(json.dumps(payload))

    vendors, offers = provider.generate(as_of=AS_OF)

    assert len(vendors) == 1
    assert vendors[0].name == "Rəşid Materials"
    assert vendors[0].data_realm == "vendor-sandbox"
    assert vendors[0].watermark == "SYNTHETIC"
    assert len(offers) == 1
    assert offers[0].material == "cement M400"
    assert offers[0].evidence_source == "napkin-ocr:42"
    assert offers[0].executable_status == "reported"
    assert offers[0].adverse_case is None


def test_generate_supports_real_production_realm_when_caller_states_it_explicitly():
    payload = {"vendor_name": "Rəşid Materials", "items": [_VALID_ITEM]}
    provider = _provider(json.dumps(payload), data_realm="vendor-production", watermark="REAL")

    vendors, offers = provider.generate(as_of=AS_OF)

    assert vendors[0].data_realm == "vendor-production"
    assert vendors[0].watermark == "REAL"
    assert offers[0].data_realm == "vendor-production"
    assert offers[0].watermark == "REAL"


def test_rejects_mismatched_realm_watermark_pairing_at_construction():
    engine: OcrEngine = _FakeOcrEngine("{}")
    with pytest.raises(ValueError):
        NapkinOcrProvider(
            ocr_engine=engine,
            image_bytes=b"x",
            mime_type="image/jpeg",
            evidence_id=1,
            data_realm="vendor-sandbox",
            watermark="REAL",
        )


def test_raises_typed_error_on_non_json_ocr_output():
    provider = _provider("not json at all")
    with pytest.raises(NapkinParseError):
        provider.generate(as_of=AS_OF)


def test_raises_typed_error_on_missing_vendor_name():
    provider = _provider(json.dumps({"items": [_VALID_ITEM]}))
    with pytest.raises(NapkinParseError):
        provider.generate(as_of=AS_OF)


def test_raises_typed_error_on_missing_items_list():
    provider = _provider(json.dumps({"vendor_name": "X"}))
    with pytest.raises(NapkinParseError):
        provider.generate(as_of=AS_OF)


def test_raises_typed_error_when_a_required_item_field_is_null():
    incomplete_item = {**_VALID_ITEM, "price": None}
    provider = _provider(json.dumps({"vendor_name": "X", "items": [incomplete_item]}))
    with pytest.raises(NapkinParseError):
        provider.generate(as_of=AS_OF)


def test_raises_typed_error_on_invalid_field_value():
    bad_item = {**_VALID_ITEM, "price": "not-a-number"}
    provider = _provider(json.dumps({"vendor_name": "X", "items": [bad_item]}))
    with pytest.raises(NapkinParseError):
        provider.generate(as_of=AS_OF)


def test_generate_is_deterministic_for_the_same_ocr_output():
    payload = {"vendor_name": "Rəşid Materials", "items": [_VALID_ITEM]}
    provider = _provider(json.dumps(payload))

    first = provider.generate(as_of=AS_OF)
    second = provider.generate(as_of=AS_OF)

    assert first == second
