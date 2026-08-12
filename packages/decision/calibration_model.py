"""Calibration-loop domain model (Phase 4, task 4.D,
TENDER_INTELLIGENCE_SPEC.md Section7.4, P319). Pure dataclasses, no DB --
packages/decision/calibration_store.py persists these.

Every field here is a fact a human already knows and enters directly (who
won, for how much, what we submitted, why we think we lost). Nothing is
scored, weighted, or derived: Section7.4's actual calibration outputs
(signal weights, per-buyer TTL/horizons, the overhead-buffer cost overlay)
all remain blocked on TBD-TIS-01/TBD-TIS-02 and are deliberately NOT
produced here (AGENTS.md hard ban #2). This module only gives the inputs a
durable, queryable home -- the same role decision_model.py's GoNoGoInputs
plays for Go/No-Go.

LOSS_REASONS' first three values are Section7.4's own verbatim categories
("проиграли дешёвому доступу конкурента" / "демпингу" / "«рисунку»"), not
an invented taxonomy. `other` is added deliberately, with a mandatory note:
forcing a real loss into one of three categories would fabricate a cause
and corrupt the loss analysis Section7.4 exists to enable. `cancelled` is
added to OUTCOME_TYPES for the same reason -- recording a cancelled tender
as `lost` would be a lie. Both additions are recorded in
docs/decisions/OPEN-QUESTIONS.md, not made silently."""

from __future__ import annotations

from dataclasses import dataclass

OUTCOME_TYPES = ("won", "lost", "cancelled")
LOSS_REASONS = ("competitor_cheap_access", "dumping", "drawn_tender", "other")


@dataclass(frozen=True)
class TenderOutcome:
    tender_id: int
    outcome: str
    our_submitted_amount: str | None
    winner_name: str | None
    winner_amount: str | None
    currency: str | None
    announced_at: str | None
    source_ref: str
    entered_by: str
    entered_at: str

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOME_TYPES:
            raise ValueError(f"unknown outcome: {self.outcome!r}")
        # INV-15/INV-16: a fact with no provenance is not a fact. A
        # human-entered outcome cannot point at a raw_snapshot (nothing
        # fetched it), so free text naming where the human saw it is the
        # honest minimum -- but it must not be blank.
        if not self.source_ref.strip():
            raise ValueError("source_ref must be non-empty (INV-15)")


@dataclass(frozen=True)
class LossReason:
    loss_reason: str
    note: str
    entered_by: str
    entered_at: str

    def __post_init__(self) -> None:
        if self.loss_reason not in LOSS_REASONS:
            raise ValueError(f"unknown loss_reason: {self.loss_reason!r}")
        if self.loss_reason == "other" and not self.note.strip():
            raise ValueError("loss_reason 'other' requires a non-empty note")
