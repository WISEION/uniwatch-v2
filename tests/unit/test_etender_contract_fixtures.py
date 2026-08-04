"""The frozen contracts must exactly match the real fixtures they were
built from — the fixtures are the ground truth (INT-01: empirical
contract, no official API docs). Pure logic + file reads only, no DB —
Fast gate."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_contract import BOM_LINES_PAGE_CONTRACT, EVENT_DETAILS_CONTRACT
from packages.tender.schema_drift import detect_schema_drift

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_bytes())


def test_event_details_contract_matches_real_capture():
    payload = _load("event_355920_details.raw.json")
    drift = detect_schema_drift(EVENT_DETAILS_CONTRACT, payload)
    assert drift.has_drift is False, drift


def test_event_details_capture_has_actual_field_values_from_the_live_source():
    payload = _load("event_355920_details.raw.json")
    assert payload["eventType"] == 7
    assert payload["organizationVoen"] == "1000418451"
    assert payload["estimatedAmount"] == 16922253.74


def test_bom_lines_contract_matches_real_capture():
    payload = _load("event_355920_bomlines_page1.raw.json")
    drift = detect_schema_drift(BOM_LINES_PAGE_CONTRACT, payload)
    assert drift.has_drift is False, drift


def test_bom_lines_capture_matches_documented_audit_facts():
    # uniwatch-v2-project.md: "event 355920 -> 4 135 bomLines over 42 pages"
    payload = _load("event_355920_bomlines_page1.raw.json")
    assert payload["totalItems"] == 4135
    assert payload["totalPages"] == 42
