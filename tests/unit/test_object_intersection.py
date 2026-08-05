"""Unit tests for the pure intersection-detection primitive (TENDER_INTELLIGENCE_SPEC.md
§5.3, P310)."""

from packages.tender.object_intersection import detect_intersection


def test_single_signal_type_is_not_composite():
    result = detect_intersection("Siyəzən", [{"signal_type": "design_tender"}])
    assert result.object_region == "Siyəzən"
    assert result.signal_types == frozenset({"design_tender"})
    assert result.is_composite is False


def test_two_distinct_signal_types_is_composite():
    result = detect_intersection(
        "Zaqatala",
        [
            {"signal_type": "design_tender"},
            {"signal_type": "design_tender"},
            {"signal_type": "procurement_plan"},
        ],
    )
    assert result.signal_types == frozenset({"design_tender", "procurement_plan"})
    assert result.is_composite is True


def test_no_signals_is_not_composite():
    result = detect_intersection("Naxçıvan", [])
    assert result.signal_types == frozenset()
    assert result.is_composite is False
