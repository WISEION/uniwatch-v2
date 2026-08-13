"""ALG-RESEARCH dossier domain model (Phase 5, task 5.A,
docs/reports/PLAN-MISSION-5.md Section3 task 5.A row 3 / master plan
Section13.3). Pure dataclass, no DB -- research_dossier_store.py persists
these. Schema rationale: docs/adr/0007-algorithm-research-dossier-schema.md.

Every field except fairness_analysis is required -- a dossier missing e.g.
its source register is not a real dossier (hard ban #3's "no silent
fallback" discipline, applied to a research artifact). This model does not
enforce ALG-RESEARCH gate R1-R12 checklist compliance or the "financial
node requires an approved dossier" rule -- that enforcement belongs to task
5.B's compiler, once it exists. This model only gives the dossier's own
shape a durable home."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ResearchDossier:
    decision_statement: str
    owners: tuple[str, ...]
    approvers: tuple[str, ...]
    source_register: tuple[dict[str, Any], ...]
    assumptions: tuple[str, ...]
    data_dictionary: dict[str, str]
    formula_or_decision_table: dict[str, Any]
    coefficients_and_rationale: dict[str, Any]
    validation_design: dict[str, Any]
    test_dataset_manifest: dict[str, Any]
    results_and_limitations: dict[str, Any]
    security_privacy_analysis: dict[str, Any]
    monitoring_criteria: dict[str, Any]
    retirement_criteria: dict[str, Any]
    created_by: str
    fairness_analysis: dict[str, Any] | None = None
    approved_at: str | None = None
    effective_from: str | None = None

    def __post_init__(self) -> None:
        if not self.decision_statement.strip():
            raise ValueError("decision_statement must be non-empty")
        if not self.owners:
            raise ValueError("owners must be non-empty")
        if not self.approvers:
            raise ValueError("approvers must be non-empty")
        if not self.source_register:
            raise ValueError("source_register must be non-empty")
