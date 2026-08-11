from __future__ import annotations

from decimal import Decimal

from packages.decision.execution_ledger_summary import summarize_deviation_category_counts, summarize_plan_fact_deltas


def _fact(**overrides) -> dict:
    defaults = {
        "boqline_source_line_id": 501,
        "planned_qty": Decimal("10"),
        "actual_qty": Decimal("15"),
        "deviation_category": "downtime",
    }
    defaults.update(overrides)
    return defaults


def test_summarize_plan_fact_deltas_computes_the_delta():
    facts = [_fact()]
    result = summarize_plan_fact_deltas(facts)
    assert result == (
        type(result[0])(boqline_source_line_id=501, planned_qty=Decimal("10"), actual_qty=Decimal("15"), delta=Decimal("5")),
    )


def test_summarize_plan_fact_deltas_excludes_facts_missing_either_side():
    facts = [_fact(planned_qty=None), _fact(boqline_source_line_id=502, actual_qty=None)]
    assert summarize_plan_fact_deltas(facts) == ()


def test_summarize_plan_fact_deltas_excludes_facts_with_no_boqline_reference():
    facts = [_fact(boqline_source_line_id=None)]
    assert summarize_plan_fact_deltas(facts) == ()


def test_summarize_plan_fact_deltas_is_sorted_by_line_id():
    facts = [_fact(boqline_source_line_id=502), _fact(boqline_source_line_id=501)]
    result = summarize_plan_fact_deltas(facts)
    assert [d.boqline_source_line_id for d in result] == [501, 502]


def test_summarize_deviation_category_counts_counts_each_category():
    facts = [_fact(deviation_category="downtime"), _fact(deviation_category="downtime"), _fact(deviation_category="rework")]
    assert summarize_deviation_category_counts(facts) == {"downtime": 2, "rework": 1}


def test_summarize_deviation_category_counts_ignores_none_category():
    facts = [_fact(deviation_category=None)]
    assert summarize_deviation_category_counts(facts) == {}
