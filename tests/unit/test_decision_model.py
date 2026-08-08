"""Unit tests for packages/decision/decision_model.py (task 4.A,
TENDER_INTELLIGENCE_SPEC.md §7.1/§8: Decision is append-only, human-authored,
ADR-0003 layer 4 / ADR-0005 human-authority-exclusive)."""

from __future__ import annotations

import pytest

from packages.decision.decision_model import DECISION_TYPES, Decision, GoNoGoInputs, LockInRequirement


def test_decision_types_are_exactly_the_five_named_in_the_spec():
    assert set(DECISION_TYPES) == {"go", "no_go", "bid", "no_bid", "conditional_bid"}


def test_decision_accepts_a_known_type():
    decision = Decision(
        tender_id=1,
        decision_type="conditional_bid",
        conditions=("lock rebar price by Friday",),
        deadline="2026-08-14T00:00:00+00:00",
        justification="91% BOQ coverage, 14-16% margin",
        actor="pm-1",
        decided_at="2026-08-08T00:00:00+00:00",
        go_no_go_inputs_id=1,
        bid_readiness_candidate_id=1,
    )
    assert decision.decision_type == "conditional_bid"


def test_decision_rejects_an_unknown_type():
    with pytest.raises(ValueError, match="unknown decision_type"):
        Decision(
            tender_id=1,
            decision_type="maybe",
            conditions=(),
            deadline=None,
            justification="x",
            actor="pm-1",
            decided_at="2026-08-08T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=None,
        )


def test_go_no_go_inputs_is_a_plain_record():
    inputs = GoNoGoInputs(
        tender_id=1,
        company_profile_notes="20 years in market",
        qualification_notes="all licenses current",
        financing_notes="bond available",
        customer_reputation_notes="pays on time historically",
        pre_designated_winner_suspected=False,
        entered_by="pm-1",
        entered_at="2026-08-08T00:00:00+00:00",
    )
    assert inputs.pre_designated_winner_suspected is False


def test_lock_in_requirement_is_a_plain_record():
    lock_in = LockInRequirement(tender_id=1, decision_id=1, boqline_source_line_id=501, vendor_id=7, vendor_name="Vendor A")
    assert lock_in.vendor_id == 7
