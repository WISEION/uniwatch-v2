"""Unit tests for the АЛГОРИТМ policy-version lifecycle transition graph
(Phase 5, task 5.A). This task's own concrete reading of
docs/reports/PLAN-MISSION-5.md Section3's stated sequence -- see
docs/decisions/OPEN-QUESTIONS.md, 2026-08-12 close-out entry."""

from __future__ import annotations

from itertools import pairwise

from packages.algorithm.policy_lifecycle import IMMUTABLE_STATUSES, can_transition


def test_happy_path_sequence_is_allowed():
    sequence = ["draft", "simulation", "business_review", "risk_review", "approved", "active", "retired"]
    for from_status, to_status in pairwise(sequence):
        assert can_transition(from_status, to_status), f"{from_status} -> {to_status} should be allowed"


def test_simulation_business_review_and_risk_review_can_reject():
    assert can_transition("simulation", "rejected")
    assert can_transition("business_review", "rejected")
    assert can_transition("risk_review", "rejected")


def test_active_can_suspend_and_suspended_can_resume_or_retire():
    assert can_transition("active", "suspended")
    assert can_transition("suspended", "active")
    assert can_transition("suspended", "retired")


def test_terminal_statuses_have_no_outgoing_transitions():
    assert not can_transition("retired", "draft")
    assert not can_transition("rejected", "draft")


def test_cannot_skip_stages():
    assert not can_transition("draft", "approved")
    assert not can_transition("draft", "active")
    assert not can_transition("simulation", "approved")


def test_cannot_go_backwards():
    assert not can_transition("approved", "risk_review")
    assert not can_transition("active", "approved")


def test_immutable_statuses_are_approved_and_active():
    assert IMMUTABLE_STATUSES == ("approved", "active")
