from __future__ import annotations

from packages.decision.reputation_feed import map_to_reputation_event_type


def test_vendor_downtime_maps_to_missed_deadline():
    assert map_to_reputation_event_type("downtime", "vendor") == "missed_deadline"


def test_vendor_last_mile_maps_to_missed_deadline():
    assert map_to_reputation_event_type("last_mile", "vendor") == "missed_deadline"


def test_vendor_rework_maps_to_quality_complaint():
    assert map_to_reputation_event_type("rework", "vendor") == "quality_complaint"


def test_vendor_preliminaries_has_no_clean_mapping():
    assert map_to_reputation_event_type("preliminaries", "vendor") is None


def test_vendor_none_category_has_no_mapping():
    assert map_to_reputation_event_type(None, "vendor") is None


def test_non_vendor_culprit_never_maps_regardless_of_category():
    assert map_to_reputation_event_type("downtime", "customer") is None
    assert map_to_reputation_event_type("rework", "internal") is None
    assert map_to_reputation_event_type("downtime", "external") is None
