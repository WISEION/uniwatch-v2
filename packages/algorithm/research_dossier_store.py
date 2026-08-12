"""Persistence for ALG-RESEARCH dossiers (Phase 5, task 5.A). Append-only:
no update/delete function -- a dossier revision is a new row, same
discipline as every other fact table in this codebase. Linking a dossier to
a policy_versions row (research_dossier_id) is the caller's job via a plain
UPDATE against policy_versions -- that FK is nullable and set-once by
design (task 5.B's compiler is what will eventually require it for
financial-impact versions, not this module)."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .research_dossier_model import ResearchDossier


def _ts(value: str | None) -> datetime | None:
    return None if value is None else datetime.fromisoformat(value)


async def store_research_dossier(conn: AsyncConnection, dossier: ResearchDossier) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO research_dossiers
                    (decision_statement, owners, approvers, source_register, assumptions,
                     data_dictionary, formula_or_decision_table, coefficients_and_rationale,
                     validation_design, test_dataset_manifest, results_and_limitations,
                     fairness_analysis, security_privacy_analysis, approved_at, effective_from,
                     monitoring_criteria, retirement_criteria, created_by)
                VALUES
                    (:decision_statement, CAST(:owners AS jsonb), CAST(:approvers AS jsonb),
                     CAST(:source_register AS jsonb), CAST(:assumptions AS jsonb),
                     CAST(:data_dictionary AS jsonb), CAST(:formula_or_decision_table AS jsonb),
                     CAST(:coefficients_and_rationale AS jsonb), CAST(:validation_design AS jsonb),
                     CAST(:test_dataset_manifest AS jsonb), CAST(:results_and_limitations AS jsonb),
                     CAST(:fairness_analysis AS jsonb), CAST(:security_privacy_analysis AS jsonb),
                     :approved_at, :effective_from, CAST(:monitoring_criteria AS jsonb),
                     CAST(:retirement_criteria AS jsonb), :created_by)
                RETURNING id
                """
            ),
            {
                "decision_statement": dossier.decision_statement,
                "owners": json.dumps(list(dossier.owners)),
                "approvers": json.dumps(list(dossier.approvers)),
                "source_register": json.dumps(list(dossier.source_register)),
                "assumptions": json.dumps(list(dossier.assumptions)),
                "data_dictionary": json.dumps(dossier.data_dictionary),
                "formula_or_decision_table": json.dumps(dossier.formula_or_decision_table),
                "coefficients_and_rationale": json.dumps(dossier.coefficients_and_rationale),
                "validation_design": json.dumps(dossier.validation_design),
                "test_dataset_manifest": json.dumps(dossier.test_dataset_manifest),
                "results_and_limitations": json.dumps(dossier.results_and_limitations),
                "fairness_analysis": json.dumps(dossier.fairness_analysis) if dossier.fairness_analysis is not None else None,
                "security_privacy_analysis": json.dumps(dossier.security_privacy_analysis),
                "approved_at": _ts(dossier.approved_at),
                "effective_from": _ts(dossier.effective_from),
                "monitoring_criteria": json.dumps(dossier.monitoring_criteria),
                "retirement_criteria": json.dumps(dossier.retirement_criteria),
                "created_by": dossier.created_by,
            },
        )
    ).scalar_one()


async def link_dossier_to_version(conn: AsyncConnection, *, policy_version_id: int, research_dossier_id: int) -> None:
    await conn.execute(
        text("UPDATE policy_versions SET research_dossier_id = :dossier_id WHERE id = :version_id"),
        {"dossier_id": research_dossier_id, "version_id": policy_version_id},
    )


async def get_research_dossier(conn: AsyncConnection, *, dossier_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, decision_statement, owners, approvers, source_register, assumptions,
                           data_dictionary, formula_or_decision_table, coefficients_and_rationale,
                           validation_design, test_dataset_manifest, results_and_limitations,
                           fairness_analysis, security_privacy_analysis, approved_at, effective_from,
                           monitoring_criteria, retirement_criteria, created_by, created_at
                    FROM research_dossiers WHERE id = :id
                    """
                ),
                {"id": dossier_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    d = dict(row)
    for key in (
        "owners",
        "approvers",
        "source_register",
        "assumptions",
        "data_dictionary",
        "formula_or_decision_table",
        "coefficients_and_rationale",
        "validation_design",
        "test_dataset_manifest",
        "results_and_limitations",
        "security_privacy_analysis",
        "monitoring_criteria",
        "retirement_criteria",
    ):
        if isinstance(d.get(key), str):
            d[key] = json.loads(d[key])
    if isinstance(d.get("fairness_analysis"), str):
        d["fairness_analysis"] = json.loads(d["fairness_analysis"])
    return d
