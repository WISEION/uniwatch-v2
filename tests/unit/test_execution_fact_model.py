from __future__ import annotations

from decimal import Decimal

import pytest

from packages.decision.execution_fact_model import CULPRIT_TYPES, DEVIATION_CATEGORIES, ExecutionFact


def _fact(**overrides) -> ExecutionFact:
    defaults = dict(
        tender_id=1,
        boqline_source_line_id=501,
        planned_qty=Decimal("10"),
        actual_qty=Decimal("15"),
        deviation_reason="crane did not arrive, half-day idle",
        deviation_category="downtime",
        culprit_type="vendor",
        culprit_vendor_name="Acme Crane Co",
        culprit_vendor_id=42,
        evidence_source="napkin-ocr:1",
        observed_at="2026-08-10T00:00:00+00:00",
    )
    defaults.update(overrides)
    return ExecutionFact(**defaults)


def test_deviation_categories_are_exactly_the_four_spec_tokens():
    assert DEVIATION_CATEGORIES == ("preliminaries", "downtime", "rework", "last_mile")


def test_culprit_types_are_exactly_the_four_named_categories():
    assert CULPRIT_TYPES == ("vendor", "customer", "internal", "external")


def test_valid_vendor_culprit_fact_constructs():
    fact = _fact()
    assert fact.culprit_type == "vendor"


def test_valid_non_vendor_culprit_fact_constructs_without_vendor_fields():
    fact = _fact(culprit_type="customer", culprit_vendor_name=None, culprit_vendor_id=None)
    assert fact.culprit_type == "customer"


def test_unknown_culprit_type_raises():
    with pytest.raises(ValueError, match="culprit_type"):
        _fact(culprit_type="weather")


def test_unknown_deviation_category_raises():
    with pytest.raises(ValueError, match="deviation_category"):
        _fact(deviation_category="scope_creep")


def test_none_deviation_category_is_allowed():
    fact = _fact(deviation_category=None)
    assert fact.deviation_category is None


def test_vendor_culprit_without_vendor_name_raises():
    with pytest.raises(ValueError, match="culprit_vendor_name"):
        _fact(culprit_vendor_name=None)


def test_non_vendor_culprit_with_vendor_name_raises():
    with pytest.raises(ValueError, match="culprit_vendor_name"):
        _fact(culprit_type="customer", culprit_vendor_id=None)


def test_non_vendor_culprit_with_vendor_id_raises():
    with pytest.raises(ValueError, match="culprit_vendor_id"):
        _fact(culprit_type="internal", culprit_vendor_name=None)
