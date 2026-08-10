"""Execution Ledger domain model (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md
Section7.3, Section8's ExecutionFact entity, ADR-0003 layers 1-3). Pure dataclass,
no DB -- packages/decision/execution_ledger_store.py persists these.

"Planned" always comes from this codebase's own stored BOQ line (never the
field-worker's photo/voice note) -- see execution_napkin_provider.py. This
module only guards that culprit_type/deviation_category are one of the
tokens TENDER_INTELLIGENCE_SPEC.md Section7.3 actually names, and that a
vendor culprit always carries a name (needed to later resolve a vendor_id,
Task 3) while a non-vendor culprit never carries vendor fields."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

DEVIATION_CATEGORIES = ("preliminaries", "downtime", "rework", "last_mile")
CULPRIT_TYPES = ("vendor", "customer", "internal", "external")


@dataclass(frozen=True)
class ExecutionFact:
    tender_id: int
    boqline_source_line_id: int | None
    planned_qty: Decimal | None
    actual_qty: Decimal | None
    deviation_reason: str
    deviation_category: str | None
    culprit_type: str
    culprit_vendor_name: str | None
    culprit_vendor_id: int | None
    evidence_source: str
    observed_at: str

    def __post_init__(self) -> None:
        if self.culprit_type not in CULPRIT_TYPES:
            raise ValueError(f"unknown culprit_type: {self.culprit_type!r}")
        if self.deviation_category is not None and self.deviation_category not in DEVIATION_CATEGORIES:
            raise ValueError(f"unknown deviation_category: {self.deviation_category!r}")
        if self.culprit_type == "vendor":
            if not self.culprit_vendor_name:
                raise ValueError("culprit_vendor_name is required when culprit_type is 'vendor'")
        else:
            if self.culprit_vendor_name is not None:
                raise ValueError("culprit_vendor_name must be None unless culprit_type is 'vendor'")
            if self.culprit_vendor_id is not None:
                raise ValueError("culprit_vendor_id must be None unless culprit_type is 'vendor'")
