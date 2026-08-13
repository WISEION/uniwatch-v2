"""Unit tests for the ALG-RESEARCH dossier domain model (Phase 5, task 5.A,
docs/adr/0007-algorithm-research-dossier-schema.md)."""

from __future__ import annotations

import pytest

from packages.algorithm.research_dossier_model import ResearchDossier


def _dossier(**overrides) -> ResearchDossier:
    base = {
        "decision_statement": "Test-only candidate algorithm B skeleton, no coefficients approved",
        "owners": ("algo_owner",),
        "approvers": ("risk_committee",),
        "source_register": ({"name": "test source", "citation": "internal test fixture"},),
        "assumptions": ("bidder pool is representative",),
        "data_dictionary": {"bid_amount": "numeric"},
        "formula_or_decision_table": {"note": "skeleton only, TBD-04 unresolved"},
        "coefficients_and_rationale": {"note": "no coefficients approved -- TBD-04"},
        "validation_design": {"method": "backtest against >=30 tenders, not yet run"},
        "test_dataset_manifest": {"tenders": []},
        "results_and_limitations": {"note": "no results yet"},
        "security_privacy_analysis": {"note": "no PII involved"},
        "monitoring_criteria": {"note": "not yet defined"},
        "retirement_criteria": {"note": "not yet defined"},
        "created_by": "algo_owner",
    }
    base.update(overrides)
    return ResearchDossier(**base)


def test_fairness_analysis_is_optional():
    dossier = _dossier()
    assert dossier.fairness_analysis is None


def test_fairness_analysis_can_be_supplied():
    dossier = _dossier(fairness_analysis={"note": "checked, no disparate impact found"})
    assert dossier.fairness_analysis == {"note": "checked, no disparate impact found"}


def test_rejects_blank_decision_statement():
    with pytest.raises(ValueError, match="decision_statement"):
        _dossier(decision_statement="  ")


def test_rejects_empty_owners():
    with pytest.raises(ValueError, match="owners"):
        _dossier(owners=())


def test_rejects_empty_approvers():
    with pytest.raises(ValueError, match="approvers"):
        _dossier(approvers=())


def test_rejects_empty_source_register():
    with pytest.raises(ValueError, match="source_register"):
        _dossier(source_register=())
