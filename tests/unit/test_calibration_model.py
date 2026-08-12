import pytest

from packages.decision.calibration_model import LOSS_REASONS, OUTCOME_TYPES, LossReason, TenderOutcome


def _outcome(**overrides):
    base = {
        "tender_id": 1,
        "outcome": "lost",
        "our_submitted_amount": "120000.00",
        "winner_name": "Rival LLC",
        "winner_amount": "98000.00",
        "currency": "AZN",
        "announced_at": "2026-08-01T00:00:00+00:00",
        "source_ref": "etender public award page, screenshot in project folder",
        "entered_by": "pm@unico.az",
        "entered_at": "2026-08-02T00:00:00+00:00",
    }
    return TenderOutcome(**{**base, **overrides})


def test_allowed_values_are_exactly_the_sourced_sets():
    assert OUTCOME_TYPES == ("won", "lost", "cancelled")
    assert LOSS_REASONS == ("competitor_cheap_access", "dumping", "drawn_tender", "other")


def test_unknown_outcome_raises_rather_than_being_accepted():
    with pytest.raises(ValueError, match="unknown outcome"):
        _outcome(outcome="probably_lost")


def test_source_ref_is_mandatory_because_INV_15_requires_provenance():
    with pytest.raises(ValueError, match="source_ref"):
        _outcome(source_ref="   ")


def test_a_won_outcome_needs_no_winner_fields():
    assert _outcome(outcome="won", winner_name=None, winner_amount=None).outcome == "won"


def test_unknown_loss_reason_raises():
    with pytest.raises(ValueError, match="unknown loss_reason"):
        LossReason(loss_reason="bad_luck", note="n", entered_by="a", entered_at="2026-08-02T00:00:00+00:00")


def test_other_loss_reason_requires_a_note_so_the_cause_is_never_blank():
    with pytest.raises(ValueError, match="note"):
        LossReason(loss_reason="other", note="  ", entered_by="a", entered_at="2026-08-02T00:00:00+00:00")
