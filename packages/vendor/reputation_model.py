"""SCG's fourth layer -- reputation facts (TENDER_INTELLIGENCE_SPEC.md
Section6.2, task 3.B). Not a rating: facts about outcomes (held price
after winning a bid, missed a deadline, quality complaint, certification
verified, financial-discipline breach, resold reserved stock under
pressure during a shortage -- the categories Section6.2 names by
example). Pure dataclass, no DB, no network -- same shape as
vendor_model.py.

INV-19 says reputation is "a trust coefficient through which every
availability status and every SCG price passes". This module only
carries the raw facts (source_ref mandatory per INV-15/INV-16). The
formula that collapses facts into that coefficient is NOT computed here
-- see docs/decisions/OPEN-QUESTIONS.md (D-VND-REP): no source document
supplies an approved weighting, and INV-19 explicitly ties it into SCG
prices, so inventing one now would be inventing a financial-adjacent
number, not just plumbing."""

from __future__ import annotations

from dataclasses import dataclass

POSITIVE_EVENT_TYPES = (
    "price_held_after_win",
    "delivered_on_time",
    "certification_verified",
)
NEGATIVE_EVENT_TYPES = (
    "price_broken_after_win",
    "missed_deadline",
    "quality_complaint",
    "financial_discipline_breach",
    "resold_reserved_stock_under_pressure",
)
REPUTATION_EVENT_TYPES = POSITIVE_EVENT_TYPES + NEGATIVE_EVENT_TYPES


def is_negative_event(event_type: str) -> bool:
    if event_type in NEGATIVE_EVENT_TYPES:
        return True
    if event_type in POSITIVE_EVENT_TYPES:
        return False
    raise ValueError(f"unknown reputation event_type: {event_type!r}")


@dataclass(frozen=True)
class ReputationFact:
    data_realm: str
    watermark: str
    vendor_name: str
    event_type: str
    project_ref: str | None
    source_ref: str
    observed_at: str
    ttl_days: int

    def __post_init__(self) -> None:
        is_negative_event(self.event_type)  # raises ValueError on an unknown type
