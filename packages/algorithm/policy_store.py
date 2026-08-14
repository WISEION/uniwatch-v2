"""Persistence for the АЛГОРИТМ policy graph (Phase 5, task 5.A,
docs/reports/PLAN-MISSION-5.md Section3).

Content immutability (FR-ALG-11) is structural: this module has no
update/delete function for policy_nodes or policy_edges. The only way to
change a version's content is fork_new_draft_version(), which copies the
current node/edge set into a brand-new draft version row. add_nodes/
add_edges additionally guard against inserting into an
approved/active version directly (defense in depth, in case a caller
reaches for them on the wrong version id -- the same discipline
packages/decision applies wherever a hard invariant can be checked before
a write rather than only relying on absence of an update path).

policy_versions.status is the one legitimately mutable column --
transition_version_status is the only function that changes it, always
through can_transition() and always logging to
policy_version_transitions.

Task 5.B layers three named, purpose-specific functions on top of
transition_version_status without changing its behavior (5.A's own tests
keep passing unmodified): submit_for_approval() gates the
risk_review->approved transition on packages/algorithm/policy_validator.py's
structural/branch-coverage checks plus two DB-backed checks this module
owns (required_role existence, financial-impact-node dossier
approval); activate_version() gates approved/suspended->active on
maker/checker (FR-ALG-12/ADR-0005) and enforces "one active version per
graph" (a courtesy on top of the migration's own partial unique index);
kill_switch() is a reason-mandatory wrapper around active->suspended."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .policy_lifecycle import can_transition
from .policy_model import IMMUTABLE_STATUSES, PolicyEdge, PolicyGraph, PolicyNode, PolicyVersion
from .policy_validator import ValidationIssue, validate_graph


class ImmutableVersionError(ValueError):
    pass


class InvalidTransitionError(ValueError):
    pass


class GraphInvalidError(ValueError):
    """Raised by submit_for_approval() -- carries every issue found (not
    just the first), matching this codebase's existing "surface everything"
    pattern (e.g. packages/decision/boq_summary.py)."""

    def __init__(self, issues: tuple[ValidationIssue, ...]) -> None:
        self.issues = issues
        super().__init__("policy version failed validation: " + "; ".join(f"{i.code}: {i.message}" for i in issues))


class MakerCheckerViolation(ValueError):
    pass


async def create_policy_graph(conn: AsyncConnection, graph: PolicyGraph) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO policy_graphs (name, description, owner)
                VALUES (:name, :description, :owner)
                RETURNING id
                """
            ),
            {"name": graph.name, "description": graph.description, "owner": graph.owner},
        )
    ).scalar_one()


async def create_draft_version(conn: AsyncConnection, *, policy_graph_id: int, version_number: int, created_by: str) -> int:
    version = PolicyVersion(
        policy_graph_id=policy_graph_id,
        version_number=version_number,
        status="draft",
        created_by=created_by,
    )
    return (
        await conn.execute(
            text(
                """
                INSERT INTO policy_versions (policy_graph_id, version_number, status, created_by)
                VALUES (:policy_graph_id, :version_number, :status, :created_by)
                RETURNING id
                """
            ),
            {
                "policy_graph_id": version.policy_graph_id,
                "version_number": version.version_number,
                "status": version.status,
                "created_by": version.created_by,
            },
        )
    ).scalar_one()


async def _get_version_status(conn: AsyncConnection, *, policy_version_id: int) -> str:
    status = (
        await conn.execute(
            text("SELECT status FROM policy_versions WHERE id = :id"),
            {"id": policy_version_id},
        )
    ).scalar_one_or_none()
    if status is None:
        raise ValueError(f"no such policy_version: {policy_version_id}")
    return str(status)


async def _assert_content_mutable(conn: AsyncConnection, *, policy_version_id: int) -> None:
    status = await _get_version_status(conn, policy_version_id=policy_version_id)
    if status in IMMUTABLE_STATUSES:
        raise ImmutableVersionError(
            f"policy_version {policy_version_id} is {status!r} -- content is immutable; use fork_new_draft_version() to change it"
        )


async def add_nodes(conn: AsyncConnection, nodes: list[PolicyNode]) -> None:
    if not nodes:
        return
    policy_version_id = nodes[0].policy_version_id
    await _assert_content_mutable(conn, policy_version_id=policy_version_id)
    for node in nodes:
        await conn.execute(
            text(
                """
                INSERT INTO policy_nodes
                    (policy_version_id, node_key, node_type, title, purpose, owner, execution_mode,
                     input_contract, output_contract, preconditions, evidence_requirements,
                     timeout_seconds, retry_policy, fallback_node_key, reason_codes, required_role,
                     financial_impact, legal_impact, model_or_policy_dependency, test_cases,
                     monitoring_metrics)
                VALUES
                    (:policy_version_id, :node_key, :node_type, :title, :purpose, :owner, :execution_mode,
                     CAST(:input_contract AS jsonb), CAST(:output_contract AS jsonb),
                     CAST(:preconditions AS jsonb), CAST(:evidence_requirements AS jsonb),
                     :timeout_seconds, CAST(:retry_policy AS jsonb), :fallback_node_key,
                     CAST(:reason_codes AS jsonb), :required_role, :financial_impact, :legal_impact,
                     :model_or_policy_dependency, CAST(:test_cases AS jsonb),
                     CAST(:monitoring_metrics AS jsonb))
                """
            ),
            {
                "policy_version_id": node.policy_version_id,
                "node_key": node.node_key,
                "node_type": node.node_type,
                "title": node.title,
                "purpose": node.purpose,
                "owner": node.owner,
                "execution_mode": node.execution_mode,
                "input_contract": json.dumps(node.input_contract),
                "output_contract": json.dumps(node.output_contract),
                "preconditions": json.dumps(list(node.preconditions)),
                "evidence_requirements": json.dumps(list(node.evidence_requirements)),
                "timeout_seconds": node.timeout_seconds,
                "retry_policy": json.dumps(node.retry_policy) if node.retry_policy is not None else None,
                "fallback_node_key": node.fallback_node_key,
                "reason_codes": json.dumps(list(node.reason_codes)),
                "required_role": node.required_role,
                "financial_impact": node.financial_impact,
                "legal_impact": node.legal_impact,
                "model_or_policy_dependency": node.model_or_policy_dependency,
                "test_cases": json.dumps(list(node.test_cases)),
                "monitoring_metrics": json.dumps(list(node.monitoring_metrics)),
            },
        )


async def add_edges(conn: AsyncConnection, edges: list[PolicyEdge]) -> None:
    if not edges:
        return
    policy_version_id = edges[0].policy_version_id
    await _assert_content_mutable(conn, policy_version_id=policy_version_id)
    for edge in edges:
        await conn.execute(
            text(
                """
                INSERT INTO policy_edges (policy_version_id, from_node_key, to_node_key, condition_label)
                VALUES (:policy_version_id, :from_node_key, :to_node_key, :condition_label)
                """
            ),
            {
                "policy_version_id": edge.policy_version_id,
                "from_node_key": edge.from_node_key,
                "to_node_key": edge.to_node_key,
                "condition_label": edge.condition_label,
            },
        )


async def fork_new_draft_version(conn: AsyncConnection, *, from_policy_version_id: int, created_by: str) -> int:
    """Copies an existing version's nodes+edges into a brand-new draft
    version of the same graph -- the only sanctioned way to change content
    once a version has progressed past draft, immutable or not."""
    row = (
        (
            await conn.execute(
                text("SELECT policy_graph_id, version_number FROM policy_versions WHERE id = :id"),
                {"id": from_policy_version_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError(f"no such policy_version: {from_policy_version_id}")

    new_version_id = await create_draft_version(
        conn,
        policy_graph_id=row["policy_graph_id"],
        version_number=row["version_number"] + 1,
        created_by=created_by,
    )

    nodes = await list_nodes(conn, policy_version_id=from_policy_version_id)
    if nodes:
        await add_nodes(
            conn,
            [PolicyNode(**{**n, "policy_version_id": new_version_id}) for n in _nodes_for_reconstruction(nodes)],
        )
    edges = await list_edges(conn, policy_version_id=from_policy_version_id)
    if edges:
        await add_edges(
            conn,
            [
                PolicyEdge(
                    policy_version_id=new_version_id,
                    from_node_key=e["from_node_key"],
                    to_node_key=e["to_node_key"],
                    condition_label=e["condition_label"],
                )
                for e in edges
            ],
        )
    return new_version_id


def _nodes_for_reconstruction(nodes: list[dict[str, Any]]) -> list[dict[str, Any]]:
    drop = {"id", "policy_version_id", "created_at"}
    reconstructed = []
    for n in nodes:
        kept = {k: v for k, v in n.items() if k not in drop}
        kept["preconditions"] = tuple(n["preconditions"])
        kept["evidence_requirements"] = tuple(n["evidence_requirements"])
        kept["reason_codes"] = tuple(n["reason_codes"])
        kept["test_cases"] = tuple(n["test_cases"])
        kept["monitoring_metrics"] = tuple(n["monitoring_metrics"])
        reconstructed.append(kept)
    return reconstructed


async def transition_version_status(
    conn: AsyncConnection, *, policy_version_id: int, to_status: str, changed_by: str, reason: str | None = None
) -> None:
    from_status = await _get_version_status(conn, policy_version_id=policy_version_id)
    if not can_transition(from_status, to_status):
        raise InvalidTransitionError(f"cannot transition {from_status!r} -> {to_status!r}")
    await conn.execute(
        text("UPDATE policy_versions SET status = :to_status WHERE id = :id"),
        {"to_status": to_status, "id": policy_version_id},
    )
    await conn.execute(
        text(
            """
            INSERT INTO policy_version_transitions (policy_version_id, from_status, to_status, changed_by, reason)
            VALUES (:policy_version_id, :from_status, :to_status, :changed_by, :reason)
            """
        ),
        {
            "policy_version_id": policy_version_id,
            "from_status": from_status,
            "to_status": to_status,
            "changed_by": changed_by,
            "reason": reason,
        },
    )


async def _unknown_role_issues(conn: AsyncConnection, nodes: list[dict[str, Any]]) -> list[ValidationIssue]:
    required_roles = {n["required_role"] for n in nodes if n.get("required_role")}
    if not required_roles:
        return []
    rows = await conn.execute(text("SELECT name FROM roles WHERE name = ANY(:names)"), {"names": list(required_roles)})
    existing = {r[0] for r in rows}
    return [
        ValidationIssue("unknown_role", f"required_role {role!r} does not exist in roles")
        for role in sorted(required_roles - existing)
    ]


async def _missing_dossier_issues(
    conn: AsyncConnection, *, policy_version_id: int, nodes: list[dict[str, Any]]
) -> list[ValidationIssue]:
    if not any(n.get("financial_impact") for n in nodes):
        return []
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT pv.research_dossier_id, rd.approved_at
                    FROM policy_versions pv
                    LEFT JOIN research_dossiers rd ON rd.id = pv.research_dossier_id
                    WHERE pv.id = :id
                    """
                ),
                {"id": policy_version_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None or row["research_dossier_id"] is None or row["approved_at"] is None:
        return [
            ValidationIssue(
                "missing_approved_dossier",
                "version has a financial_impact node but no linked, approved research dossier",
            )
        ]
    return []


async def submit_for_approval(
    conn: AsyncConnection, *, policy_version_id: int, changed_by: str, reason: str | None = None
) -> None:
    """FR-ALG-03/FR-ALG-04/FR-ALG-20's gate -- the one blocking point before
    a version may reach `approved`. Nothing is written if any issue is
    found; GraphInvalidError carries the complete list."""
    nodes = await list_nodes(conn, policy_version_id=policy_version_id)
    edges = await list_edges(conn, policy_version_id=policy_version_id)

    issues = list(validate_graph(nodes, edges))
    issues += await _unknown_role_issues(conn, nodes)
    issues += await _missing_dossier_issues(conn, policy_version_id=policy_version_id, nodes=nodes)

    if issues:
        raise GraphInvalidError(tuple(issues))

    await transition_version_status(
        conn, policy_version_id=policy_version_id, to_status="approved", changed_by=changed_by, reason=reason
    )


async def activate_version(conn: AsyncConnection, *, policy_version_id: int, changed_by: str, reason: str | None = None) -> None:
    """FR-ALG-12/ADR-0005's activation gate + "one active version per
    graph" (structurally guaranteed by migrations/0019's partial unique
    index; the auto-suspend below is a courtesy that keeps the common path
    from ever hitting it, not the enforcement itself). can_transition
    (inside transition_version_status) already rejects activating a
    version that isn't currently approved/suspended -- this is also how
    rollback works: calling this against a suspended version is exactly
    "reactivate a previously-active version"."""
    row = (
        (
            await conn.execute(
                text("SELECT policy_graph_id, created_by FROM policy_versions WHERE id = :id"),
                {"id": policy_version_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError(f"no such policy_version: {policy_version_id}")

    nodes = await list_nodes(conn, policy_version_id=policy_version_id)
    if any(n.get("financial_impact") for n in nodes) and changed_by == row["created_by"]:
        raise MakerCheckerViolation(
            f"activator {changed_by!r} is the same identity that designed this financial-impact "
            "version (FR-ALG-12/ADR-0005 requires two distinct identities)"
        )

    current_active = (
        await conn.execute(
            text("SELECT id FROM policy_versions WHERE policy_graph_id = :graph_id AND status = 'active'"),
            {"graph_id": row["policy_graph_id"]},
        )
    ).scalar_one_or_none()
    if current_active is not None and current_active != policy_version_id:
        await transition_version_status(
            conn,
            policy_version_id=current_active,
            to_status="suspended",
            changed_by=changed_by,
            reason=f"superseded by activation of policy_version {policy_version_id}",
        )

    await transition_version_status(
        conn, policy_version_id=policy_version_id, to_status="active", changed_by=changed_by, reason=reason
    )


async def kill_switch(conn: AsyncConnection, *, policy_version_id: int, changed_by: str, reason: str) -> None:
    """FR-ALG-13 -- a reason-mandatory, clearly-named wrapper around
    active->suspended. Only the "stop new evaluations" half is built: this
    codebase has no evaluation/execution engine yet, so "in-flight
    evaluations complete in a defined way" has nothing to act on (recorded
    as a real gap in docs/decisions/OPEN-QUESTIONS.md, not fabricated)."""
    if not reason.strip():
        raise ValueError("kill_switch requires a non-empty reason")
    status = await _get_version_status(conn, policy_version_id=policy_version_id)
    if status != "active":
        raise ValueError(f"kill_switch requires an active version; policy_version {policy_version_id} is {status!r}")
    await transition_version_status(
        conn, policy_version_id=policy_version_id, to_status="suspended", changed_by=changed_by, reason=reason
    )


async def list_nodes(conn: AsyncConnection, *, policy_version_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_version_id, node_key, node_type, title, purpose, owner, execution_mode,
                           input_contract, output_contract, preconditions, evidence_requirements,
                           timeout_seconds, retry_policy, fallback_node_key, reason_codes, required_role,
                           financial_impact, legal_impact, model_or_policy_dependency, test_cases,
                           monitoring_metrics, created_at
                    FROM policy_nodes WHERE policy_version_id = :policy_version_id ORDER BY id
                    """
                ),
                {"policy_version_id": policy_version_id},
            )
        )
        .mappings()
        .all()
    )
    results = []
    for row in rows:
        d = dict(row)
        for key in (
            "input_contract",
            "output_contract",
            "preconditions",
            "evidence_requirements",
            "reason_codes",
            "test_cases",
            "monitoring_metrics",
        ):
            d[key] = json.loads(d[key]) if isinstance(d[key], str) else d[key]
        if isinstance(d.get("retry_policy"), str):
            d["retry_policy"] = json.loads(d["retry_policy"])
        results.append(d)
    return results


async def list_edges(conn: AsyncConnection, *, policy_version_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_version_id, from_node_key, to_node_key, condition_label, created_at
                    FROM policy_edges WHERE policy_version_id = :policy_version_id ORDER BY id
                    """
                ),
                {"policy_version_id": policy_version_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def get_version(conn: AsyncConnection, *, policy_version_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_graph_id, version_number, status, research_dossier_id, created_by, created_at
                    FROM policy_versions WHERE id = :id
                    """
                ),
                {"id": policy_version_id},
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None


async def list_versions_by_graph(conn: AsyncConnection, *, policy_graph_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_graph_id, version_number, status, research_dossier_id, created_by, created_at
                    FROM policy_versions WHERE policy_graph_id = :policy_graph_id ORDER BY version_number
                    """
                ),
                {"policy_graph_id": policy_graph_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def list_transitions_by_version(conn: AsyncConnection, *, policy_version_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, policy_version_id, from_status, to_status, changed_by, changed_at, reason
                    FROM policy_version_transitions WHERE policy_version_id = :policy_version_id ORDER BY id
                    """
                ),
                {"policy_version_id": policy_version_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
