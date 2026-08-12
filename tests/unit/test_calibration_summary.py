from decimal import Decimal

from packages.decision.calibration_summary import compare_winner_to_our_basis, summarize_loss_reasons


def test_comparison_carries_the_coverage_it_was_computed_over():
    c = compare_winner_to_our_basis(
        winner_amount=Decimal("98000"),
        our_submitted_amount=Decimal("120000"),
        our_scg_cost_basis=Decimal("90000"),
        priced_line_count=17,
        total_line_count=20,
    )
    assert c.winner_vs_our_submitted == Decimal("-22000")
    assert c.winner_vs_our_cost_basis == Decimal("8000")
    assert c.coverage_line_count == 17
    assert c.total_line_count == 20
    assert c.is_partial_coverage is True


def test_full_coverage_is_flagged_as_not_partial():
    c = compare_winner_to_our_basis(
        winner_amount=Decimal("1"),
        our_submitted_amount=Decimal("1"),
        our_scg_cost_basis=Decimal("1"),
        priced_line_count=5,
        total_line_count=5,
    )
    assert c.is_partial_coverage is False


def test_a_missing_winner_amount_yields_none_deltas_not_zero():
    """Hard ban #3: unknown is not zero. A winner whose price we do not
    know must not read as 'they bid nothing'."""
    c = compare_winner_to_our_basis(
        winner_amount=None,
        our_submitted_amount=Decimal("120000"),
        our_scg_cost_basis=Decimal("90000"),
        priced_line_count=17,
        total_line_count=20,
    )
    assert c.winner_vs_our_submitted is None
    assert c.winner_vs_our_cost_basis is None
    # The operand we DO have is still reported -- a missing operand does not
    # blank the whole comparison.
    assert c.our_submitted_amount == Decimal("120000")


def test_no_ratio_is_exposed_without_coverage_travelling_with_it():
    c = compare_winner_to_our_basis(
        winner_amount=Decimal("98000"),
        our_submitted_amount=Decimal("120000"),
        our_scg_cost_basis=Decimal("90000"),
        priced_line_count=1,
        total_line_count=20,
    )
    # 1 of 20 lines priced: the delta exists but must be marked partial so
    # no caller can read it as a whole-tender margin.
    assert c.is_partial_coverage is True


def test_loss_reason_rollup_counts_each_category():
    rows = [{"loss_reason": "dumping"}, {"loss_reason": "dumping"}, {"loss_reason": "drawn_tender"}]
    assert summarize_loss_reasons(rows) == {"dumping": 2, "drawn_tender": 1}


def test_loss_reason_rollup_of_nothing_is_empty_not_a_zero_filled_shape():
    assert summarize_loss_reasons([]) == {}
