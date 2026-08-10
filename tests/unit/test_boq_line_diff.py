from __future__ import annotations

from decimal import Decimal

from packages.tender.boq_line_diff import diff_boq_lines
from packages.tender.boq_line_model import BoqLine


def _line(source_line_id: int, **overrides) -> BoqLine:
    defaults = {
        "source_line_id": source_line_id,
        "page_number": 1,
        "section": None,
        "category_code": None,
        "description": "rebar-12mm",
        "unit_raw": "t",
        "unit_canonical": "t",
        "unit_status": "mapped",
        "qty": Decimal("10"),
        "line_type": "normal",
        "spec_requirements": (),
        "rate": Decimal("850"),
        "amount": Decimal("8500"),
    }
    defaults.update(overrides)
    return BoqLine(**defaults)


def test_diff_boq_lines_empty_for_identical_sets():
    lines = [_line(1), _line(2)]
    assert diff_boq_lines(lines, list(lines)) == ()


def test_diff_boq_lines_detects_a_changed_quantity():
    old = [_line(1, qty=Decimal("10"))]
    new = [_line(1, qty=Decimal("15"))]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_a_changed_amount():
    old = [_line(1, amount=Decimal("8500"))]
    new = [_line(1, amount=Decimal("9000"))]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_a_changed_description():
    old = [_line(1, description="rebar-12mm")]
    new = [_line(1, description="rebar-14mm")]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_an_added_line():
    old = [_line(1)]
    new = [_line(1), _line(2)]
    assert diff_boq_lines(old, new) == (2,)


def test_diff_boq_lines_detects_a_removed_line():
    old = [_line(1), _line(2)]
    new = [_line(1)]
    assert diff_boq_lines(old, new) == (2,)


def test_diff_boq_lines_result_is_sorted():
    old = []
    new = [_line(5), _line(1), _line(3)]
    assert diff_boq_lines(old, new) == (1, 3, 5)


def test_diff_boq_lines_detects_a_changed_rate():
    old = [_line(1, rate=Decimal("850"))]
    new = [_line(1, rate=Decimal("900"))]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_a_changed_unit_raw():
    old = [_line(1, unit_raw="t")]
    new = [_line(1, unit_raw="kg")]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_ignores_unit_canonical_and_status_and_page_number():
    # unit_canonical/unit_status/page_number are derived/positional, not
    # substantive content -- a line that only differs there (e.g. a
    # re-canonicalization improvement) is not a real BOQ change.
    old = [_line(1, unit_canonical="t", unit_status="mapped", page_number=1)]
    new = [_line(1, unit_canonical=None, unit_status="unmapped", page_number=2)]
    assert diff_boq_lines(old, new) == ()
