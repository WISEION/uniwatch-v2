"""Unit tests for packages/decision/boq_summary.py (task 3.D, P315:
"выдаётся сводка «X% зелёного / Y% жёлтого / Z% красного по деньгам»")."""

from __future__ import annotations

from decimal import Decimal

import pytest

from packages.decision.boq_summary import summarize_boq_matches
from packages.decision.matching import BoqLineMatch
from packages.tender.boq_line_model import BoqLine


def _boq_line(source_line_id: int, amount: str | None, line_type: str = "normal") -> BoqLine:
    return BoqLine(
        source_line_id=source_line_id,
        page_number=1,
        section=None,
        category_code=None,
        description="line",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("1"),
        line_type=line_type,
        spec_requirements=(),
        rate=Decimal("100") if amount is not None else None,
        amount=Decimal(amount) if amount is not None else None,
    )


def _match(source_line_id: int, traffic_light: str) -> BoqLineMatch:
    return BoqLineMatch(
        boqline_source_line_id=source_line_id,
        traffic_light=traffic_light,
        candidates=(),
        ranked_executable=(),
    )


def test_summarize_boq_matches_computes_percentage_by_money():
    boq_lines = [_boq_line(1, "600"), _boq_line(2, "300"), _boq_line(3, "100")]
    matches = {1: _match(1, "green"), 2: _match(2, "yellow"), 3: _match(3, "red")}

    summary = summarize_boq_matches(boq_lines, matches)

    assert summary.green_amount == Decimal("600")
    assert summary.yellow_amount == Decimal("300")
    assert summary.red_amount == Decimal("100")
    assert summary.total_priced_amount == Decimal("1000")
    assert summary.green_pct == 60.0
    assert summary.yellow_pct == 30.0
    assert summary.red_pct == 10.0


def test_summarize_boq_matches_surfaces_unpriced_lines_without_hiding_them():
    boq_lines = [_boq_line(1, "600"), _boq_line(2, None), _boq_line(3, None)]
    matches = {1: _match(1, "green"), 2: _match(2, "red"), 3: _match(3, "yellow")}

    summary = summarize_boq_matches(boq_lines, matches)

    assert summary.unpriced_line_count == 2
    assert summary.total_priced_amount == Decimal("600")
    assert summary.green_pct == 100.0


def test_summarize_boq_matches_excludes_non_matchable_line_types_from_percentages():
    boq_lines = [
        _boq_line(1, "600", line_type="normal"),
        _boq_line(2, "300", line_type="normal"),
        _boq_line(3, "9999", line_type="preliminaries"),
    ]
    matches = {1: _match(1, "green"), 2: _match(2, "yellow")}

    summary = summarize_boq_matches(boq_lines, matches)

    assert summary.non_matchable_line_count == 1
    assert summary.non_matchable_amount == Decimal("9999")
    assert summary.total_priced_amount == Decimal("900")
    assert summary.green_pct == pytest.approx(66.666666, rel=1e-4)


def test_summarize_boq_matches_does_not_invent_an_amount_for_an_unpriced_non_matchable_line():
    # A non-matchable line can also lack a source-supplied amount -- that
    # money is honestly absent, not zero, so it must not be summed into
    # non_matchable_amount (same "don't invent a number" reasoning
    # unpriced_line_count already applies to matchable lines).
    boq_lines = [
        _boq_line(1, "600", line_type="normal"),
        _boq_line(2, None, line_type="preliminaries"),
    ]
    matches = {1: _match(1, "green")}

    summary = summarize_boq_matches(boq_lines, matches)

    assert summary.non_matchable_line_count == 1
    assert summary.non_matchable_amount == Decimal("0")
