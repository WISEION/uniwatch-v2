"""INT-01, INT-02: the World Bank Projects API donor-pipeline contract
must match the two real, live-captured fixtures exactly -- both at the
page level and for every project item inside them."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.schema_drift import detect_schema_drift, detect_schema_drift_over_items
from packages.tender.worldbank_contract import DONOR_PIPELINE_PAGE_CONTRACT, DONOR_PIPELINE_PROJECT_CONTRACT

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "worldbank"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_page_os0_fixture_is_drift_free():
    payload = _load("az_donor_pipeline_page_os0.raw.json")
    drift = detect_schema_drift(DONOR_PIPELINE_PAGE_CONTRACT, payload)
    assert not drift.has_drift, drift


def test_page_os10_fixture_is_drift_free():
    payload = _load("az_donor_pipeline_page_os10.raw.json")
    drift = detect_schema_drift(DONOR_PIPELINE_PAGE_CONTRACT, payload)
    assert not drift.has_drift, drift


def test_every_project_item_in_both_pages_is_drift_free():
    for name in ("az_donor_pipeline_page_os0.raw.json", "az_donor_pipeline_page_os10.raw.json"):
        payload = _load(name)
        projects = list(payload["projects"].values())
        drift = detect_schema_drift_over_items(DONOR_PIPELINE_PROJECT_CONTRACT, projects)
        assert not drift.has_drift, f"{name}: {drift}"
