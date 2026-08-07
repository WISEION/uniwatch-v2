"""Executable Availability (TENDER_INTELLIGENCE_SPEC.md §6.3, task 3.C,
P314): availability is not binary. Four graduated tiers, strongest to
weakest -- `reserved` (legally locked volume+price), `confirmed`
(physically confirmed, not locked), `reported` (declared by the vendor,
unverified), `unknown`.

INV-19 says reputation is "a trust coefficient through which every
availability status and every SCG price passes". The actual numeric
coefficient is `D-VND-REP` (docs/decisions/OPEN-QUESTIONS.md) -- still
unresolved, and this module does not invent it (AGENTS.md hard ban #2).
What IS given, in the spec's own words, is a qualitative example: "Reserved
у ненадёжного ≈ Confirmed у надёжного" (an unreliable vendor's Reserved
claim is worth about as much as a reliable vendor's Confirmed claim).
`effective_executable_status()` implements exactly that one stated rule --
a one-tier downgrade when the vendor carries a negative `ReputationFact`
(packages/vendor/reputation_model.py) -- and nothing more: no symmetric
upgrade for positive reputation, since the spec never states one, and no
numeric weighting. `unknown` has no lower tier to downgrade to and stays
`unknown` regardless of reputation."""

from __future__ import annotations

EXECUTABLE_STATUS_TIERS = ("reserved", "confirmed", "reported", "unknown")


def is_valid_executable_status(status: str) -> bool:
    if status in EXECUTABLE_STATUS_TIERS:
        return True
    raise ValueError(f"unknown executable_status: {status!r}")


def effective_executable_status(raw_status: str, *, has_negative_reputation: bool) -> str:
    is_valid_executable_status(raw_status)
    if not has_negative_reputation:
        return raw_status
    index = EXECUTABLE_STATUS_TIERS.index(raw_status)
    downgraded_index = min(index + 1, len(EXECUTABLE_STATUS_TIERS) - 1)
    return EXECUTABLE_STATUS_TIERS[downgraded_index]
