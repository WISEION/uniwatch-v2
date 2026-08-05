"""INT-01, INT-02: the eTender procurement-plan list contract must match
the two real, live-captured fixtures exactly -- both at the page level
and for every plan item inside them."""

from __future__ import annotations

import json

from source_fixtures import ETENDER_FIXTURES

from packages.tender.etender_contract import APP_ITEM_CONTRACT, APP_LIST_PAGE_CONTRACT
from packages.tender.schema_drift import detect_schema_drift, detect_schema_drift_over_items


def _load(name: str) -> dict:
    return json.loads((ETENDER_FIXTURES / name).read_text())


def test_page1_fixture_is_drift_free():
    payload = _load("app_list_page1_2026.raw.json")
    assert not detect_schema_drift(APP_LIST_PAGE_CONTRACT, payload).has_drift


def test_zaqatala_fixture_is_drift_free():
    payload = _load("app_list_zaqatala_2026.raw.json")
    assert not detect_schema_drift(APP_LIST_PAGE_CONTRACT, payload).has_drift


def test_every_item_in_both_pages_is_drift_free():
    for name in ("app_list_page1_2026.raw.json", "app_list_zaqatala_2026.raw.json"):
        payload = _load(name)
        drift = detect_schema_drift_over_items(APP_ITEM_CONTRACT, payload["items"])
        assert not drift.has_drift, f"{name}: {drift}"
