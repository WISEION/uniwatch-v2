"""Unit tests for packages/vendor/availability_model.py (task 3.C,
TENDER_INTELLIGENCE_SPEC.md §6.3, P314). Pure functions, no DB."""

from __future__ import annotations

import pytest

from packages.vendor.availability_model import (
    EXECUTABLE_STATUS_TIERS,
    effective_executable_status,
    is_valid_executable_status,
)


def test_tier_ordering_is_strongest_to_weakest():
    assert EXECUTABLE_STATUS_TIERS == ("reserved", "confirmed", "reported", "unknown")


@pytest.mark.parametrize("status", ["reserved", "confirmed", "reported", "unknown"])
def test_every_real_tier_is_valid(status):
    assert is_valid_executable_status(status) is True


def test_unknown_status_raises():
    with pytest.raises(ValueError):
        is_valid_executable_status("verified")


def test_no_negative_reputation_leaves_raw_status_unchanged():
    for status in EXECUTABLE_STATUS_TIERS:
        assert effective_executable_status(status, has_negative_reputation=False) == status


def test_negative_reputation_downgrades_reserved_to_confirmed():
    # TENDER_INTELLIGENCE_SPEC.md §6.3's own stated example: "Reserved у
    # ненадёжного ≈ Confirmed у надёжного" -- an unreliable vendor's
    # "reserved" claim is worth about as much as a reliable vendor's
    # "confirmed" claim.
    assert effective_executable_status("reserved", has_negative_reputation=True) == "confirmed"


def test_negative_reputation_downgrades_confirmed_to_reported():
    assert effective_executable_status("confirmed", has_negative_reputation=True) == "reported"


def test_negative_reputation_downgrades_reported_to_unknown():
    assert effective_executable_status("reported", has_negative_reputation=True) == "unknown"


def test_negative_reputation_cannot_downgrade_below_unknown():
    assert effective_executable_status("unknown", has_negative_reputation=True) == "unknown"


def test_same_raw_status_yields_different_effective_status_by_reliability():
    # P314's acceptance criterion in one assertion: identical words, two
    # different effective outcomes, purely as a function of reputation.
    reliable = effective_executable_status("reserved", has_negative_reputation=False)
    unreliable = effective_executable_status("reserved", has_negative_reputation=True)
    assert reliable != unreliable


def test_invalid_raw_status_raises_before_considering_reputation():
    with pytest.raises(ValueError):
        effective_executable_status("verified", has_negative_reputation=True)
