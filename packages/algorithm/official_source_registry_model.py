"""Official-source registry domain model (Phase 5, task 5.A,
docs/reports/PLAN-MISSION-5.md Section3 task 5.A row 4, FR-ALG-23). Pure
dataclass, no DB -- official_source_registry_store.py persists these.

This is a structural home for real, human-sourced, cited facts (an actual
law, an actual CBAR FX rate, an actual VAT percentage) entered later with
their own citation and effective date -- this task's own code seeds zero
rows and this model does not carry an example/default value. `value` is a
plain string deliberately: a law citation is not a number at all, and this
task does not decide a numeric type/precision for FX/VAT/price-index values
without a real source to derive one from."""

from __future__ import annotations

from dataclasses import dataclass

SOURCE_TYPES = ("law", "fx_rate", "vat_rate", "price_index")


@dataclass(frozen=True)
class OfficialSource:
    source_type: str
    name: str
    citation: str
    value: str
    effective_from: str
    entered_by: str
    entered_at: str
    effective_to: str | None = None

    def __post_init__(self) -> None:
        if self.source_type not in SOURCE_TYPES:
            raise ValueError(f"unknown source_type: {self.source_type!r}")
        if not self.citation.strip():
            raise ValueError("citation must be non-empty (INV-15: a sourced fact needs its source)")
        if not self.value.strip():
            raise ValueError("value must be non-empty")
