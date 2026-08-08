"""Decision Core domain model (task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1,
§8's `Decision` entity, ADR-0003 layer 4, ADR-0005). Pure dataclasses, no
DB -- packages/decision/decision_store.py persists these.

`Decision` is append-only by construction of the store layer (no UPDATE
statement exists for it) -- this module only guards that `decision_type`
is one of the five values TENDER_INTELLIGENCE_SPEC.md §7.1 actually names
(Go/No-Go's two, Bid/No-Bid/Conditional's three), raising rather than
silently accepting an arbitrary string (AGENTS.md hard ban #3).

`GoNoGoInputs` carries only free-text notes for qualification/financing/
customer-reputation/pre-designated-winner-suspicion -- none of these are
scored or weighted here. No source document supplies a scoring formula for
any of them (customer reputation specifically depends on Phase 4.C's
Execution Ledger, which does not exist yet), so a human enters an
assessment as text and makes the actual Go/No-Go call themselves; this
module only gives that assessment a durable, queryable home."""

from __future__ import annotations

from dataclasses import dataclass

DECISION_TYPES = ("go", "no_go", "bid", "no_bid", "conditional_bid")


@dataclass(frozen=True)
class GoNoGoInputs:
    tender_id: int
    company_profile_notes: str
    qualification_notes: str
    financing_notes: str
    customer_reputation_notes: str
    pre_designated_winner_suspected: bool
    entered_by: str
    entered_at: str


@dataclass(frozen=True)
class Decision:
    tender_id: int
    decision_type: str
    conditions: tuple[str, ...]
    deadline: str | None
    justification: str
    actor: str
    decided_at: str
    go_no_go_inputs_id: int | None
    bid_readiness_candidate_id: int | None

    def __post_init__(self) -> None:
        if self.decision_type not in DECISION_TYPES:
            raise ValueError(f"unknown decision_type: {self.decision_type!r}")


@dataclass(frozen=True)
class LockInRequirement:
    tender_id: int
    decision_id: int
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str
