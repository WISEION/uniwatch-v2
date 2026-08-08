"""Decision Core persistence (task 4.A). Append-only for `decisions` --
no UPDATE/DELETE statement against that table is ever issued here."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .bid_readiness import BidReadinessCandidate
from .decision_model import Decision, GoNoGoInputs


async def store_go_no_go_inputs(conn: AsyncConnection, inputs: GoNoGoInputs) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO go_no_go_inputs
                    (tender_id, company_profile_notes, qualification_notes, financing_notes,
                     customer_reputation_notes, pre_designated_winner_suspected, entered_by, entered_at)
                VALUES (:tender_id, :company_profile_notes, :qualification_notes, :financing_notes,
                        :customer_reputation_notes, :pre_designated_winner_suspected, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "tender_id": inputs.tender_id,
                "company_profile_notes": inputs.company_profile_notes,
                "qualification_notes": inputs.qualification_notes,
                "financing_notes": inputs.financing_notes,
                "customer_reputation_notes": inputs.customer_reputation_notes,
                "pre_designated_winner_suspected": inputs.pre_designated_winner_suspected,
                "entered_by": inputs.entered_by,
                "entered_at": datetime.fromisoformat(inputs.entered_at),
            },
        )
    ).scalar_one()


async def load_go_no_go_inputs(conn: AsyncConnection, inputs_id: int) -> dict[str, Any] | None:
    row = (
        (await conn.execute(text("SELECT id, tender_id FROM go_no_go_inputs WHERE id = :id"), {"id": inputs_id}))
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


async def store_bid_readiness_candidate(conn: AsyncConnection, candidate: BidReadinessCandidate) -> int:
    critical_lines_json = json.dumps(
        [
            {"boqline_source_line_id": cl.boqline_source_line_id, "vendor_id": cl.vendor_id, "vendor_name": cl.vendor_name}
            for cl in candidate.critical_lines
        ]
    )
    return (
        await conn.execute(
            text(
                """
                INSERT INTO bid_readiness_candidates
                    (tender_id, green_amount, yellow_amount, red_amount, unpriced_line_count,
                     non_matchable_line_count, non_matchable_amount, total_priced_amount,
                     green_pct, yellow_pct, red_pct, is_lottery, critical_lines, computed_at)
                VALUES (:tender_id, :green_amount, :yellow_amount, :red_amount, :unpriced_line_count,
                        :non_matchable_line_count, :non_matchable_amount, :total_priced_amount,
                        :green_pct, :yellow_pct, :red_pct, :is_lottery, CAST(:critical_lines AS jsonb), :computed_at)
                RETURNING id
                """
            ),
            {
                "tender_id": candidate.tender_id,
                "green_amount": candidate.summary.green_amount,
                "yellow_amount": candidate.summary.yellow_amount,
                "red_amount": candidate.summary.red_amount,
                "unpriced_line_count": candidate.summary.unpriced_line_count,
                "non_matchable_line_count": candidate.summary.non_matchable_line_count,
                "non_matchable_amount": candidate.summary.non_matchable_amount,
                "total_priced_amount": candidate.summary.total_priced_amount,
                "green_pct": candidate.summary.green_pct,
                "yellow_pct": candidate.summary.yellow_pct,
                "red_pct": candidate.summary.red_pct,
                "is_lottery": candidate.is_lottery,
                "critical_lines": critical_lines_json,
                "computed_at": datetime.fromisoformat(candidate.computed_at),
            },
        )
    ).scalar_one()


async def load_bid_readiness_candidate(conn: AsyncConnection, candidate_id: int) -> dict[str, Any]:
    row = (
        (
            await conn.execute(
                text("SELECT id, tender_id, critical_lines FROM bid_readiness_candidates WHERE id = :id"),
                {"id": candidate_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError(f"bid readiness candidate {candidate_id} not found")
    result = dict(row)
    if isinstance(result["critical_lines"], str):
        result["critical_lines"] = json.loads(result["critical_lines"])
    return result


async def store_decision(conn: AsyncConnection, decision: Decision) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO decisions
                    (tender_id, decision_type, conditions, deadline, justification, actor, decided_at,
                     go_no_go_inputs_id, bid_readiness_candidate_id)
                VALUES (:tender_id, :decision_type, CAST(:conditions AS jsonb), :deadline, :justification, :actor,
                        :decided_at, :go_no_go_inputs_id, :bid_readiness_candidate_id)
                RETURNING id
                """
            ),
            {
                "tender_id": decision.tender_id,
                "decision_type": decision.decision_type,
                "conditions": json.dumps(list(decision.conditions)),
                "deadline": datetime.fromisoformat(decision.deadline) if decision.deadline else None,
                "justification": decision.justification,
                "actor": decision.actor,
                "decided_at": datetime.fromisoformat(decision.decided_at),
                "go_no_go_inputs_id": decision.go_no_go_inputs_id,
                "bid_readiness_candidate_id": decision.bid_readiness_candidate_id,
            },
        )
    ).scalar_one()


async def store_lock_in_requirement(
    conn: AsyncConnection,
    *,
    tender_id: int,
    decision_id: int,
    boqline_source_line_id: int,
    vendor_id: int,
    vendor_name: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO lock_in_requirements
                    (tender_id, decision_id, boqline_source_line_id, vendor_id, vendor_name)
                VALUES (:tender_id, :decision_id, :boqline_source_line_id, :vendor_id, :vendor_name)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "decision_id": decision_id,
                "boqline_source_line_id": boqline_source_line_id,
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
            },
        )
    ).scalar_one()


async def list_lock_in_requirements_by_tender(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, decision_id, boqline_source_line_id, vendor_id, vendor_name, status, created_at
                    FROM lock_in_requirements WHERE tender_id = :tender_id ORDER BY id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
