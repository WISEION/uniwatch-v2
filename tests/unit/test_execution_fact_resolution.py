from __future__ import annotations

from decimal import Decimal

from packages.decision.execution_fact_resolution import resolve_boqline_reference, resolve_vendor_reference
from packages.tender.boq_line_model import BoqLine


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


def test_resolve_boqline_reference_matches_a_substring_case_insensitively():
    lines = [_line(1, "Rebar 12mm, grade B500B"), _line(2, "Concrete C25/30")]
    result = resolve_boqline_reference(lines, "rebar 12mm")
    assert result is not None
    assert result.source_line_id == 1


def test_resolve_boqline_reference_returns_none_when_no_match():
    lines = [_line(1, "Rebar 12mm")]
    assert resolve_boqline_reference(lines, "excavator rental") is None


def test_resolve_boqline_reference_returns_none_for_none_description():
    lines = [_line(1, "Rebar 12mm")]
    assert resolve_boqline_reference(lines, None) is None


def test_resolve_boqline_reference_returns_first_match_when_ambiguous():
    lines = [_line(1, "Rebar 12mm"), _line(2, "Rebar 12mm secondary batch")]
    result = resolve_boqline_reference(lines, "rebar 12mm")
    assert result is not None
    assert result.source_line_id == 1


def test_resolve_vendor_reference_matches_case_insensitively():
    lock_ins = [
        {"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"},
        {"boqline_source_line_id": 2, "vendor_id": 43, "vendor_name": "Beta Rebar Supply"},
    ]
    assert resolve_vendor_reference(lock_ins, "acme crane co") == 42


def test_resolve_vendor_reference_returns_none_when_no_match():
    lock_ins = [{"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"}]
    assert resolve_vendor_reference(lock_ins, "Unknown Supplier LLC") is None


def test_resolve_vendor_reference_returns_none_for_none_name():
    lock_ins = [{"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"}]
    assert resolve_vendor_reference(lock_ins, None) is None


def test_resolve_vendor_reference_returns_none_for_empty_lock_ins():
    assert resolve_vendor_reference([], "Acme Crane Co") is None
