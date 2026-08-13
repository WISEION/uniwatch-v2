"""АЛГОРИТМ policy-graph domain model (Phase 5, task 5.A,
docs/reports/PLAN-MISSION-5.md Section3). Pure dataclasses, no DB --
policy_store.py persists these.

A PolicyGraph is a stable named identity; PolicyVersion is the actual
versioned, lifecycle-tracked content (nodes + edges). Content on an
approved/active version is immutable -- enforced structurally in
policy_store.py (no update/delete function exists for policy_nodes/
policy_edges), not merely documented here.

ml/hybrid node types are representable (FR-ALG-08: the schema must not need
a migration when Phase 8 eventually activates them) but PolicyNode rejects
constructing one in this task -- there is no compiler yet (task 5.B) to
gate activation, so the model layer is this task's own enforcement point.

Nothing here invents a coefficient, weight, or threshold. input_contract/
output_contract/preconditions/evidence_requirements/reason_codes/
test_cases/monitoring_metrics are all structural placeholders (dict/tuple
shapes) a real node definition fills in later -- D-FIN/TBD-04 remain
untouched."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

NODE_TYPES = ("human", "rule", "gate", "data_quality", "ml", "hybrid")
ACTIVATABLE_NODE_TYPES = ("human", "rule", "gate", "data_quality")

LIFECYCLE_STATUSES = (
    "draft",
    "simulation",
    "business_review",
    "risk_review",
    "approved",
    "active",
    "retired",
    "rejected",
    "suspended",
)
IMMUTABLE_STATUSES = ("approved", "active")


@dataclass(frozen=True)
class PolicyGraph:
    name: str
    owner: str
    description: str | None = None


@dataclass(frozen=True)
class PolicyVersion:
    policy_graph_id: int
    version_number: int
    status: str
    created_by: str
    research_dossier_id: int | None = None

    def __post_init__(self) -> None:
        if self.status not in LIFECYCLE_STATUSES:
            raise ValueError(f"unknown lifecycle status: {self.status!r}")
        if self.version_number < 1:
            raise ValueError("version_number must be >= 1")


@dataclass(frozen=True)
class PolicyNode:
    policy_version_id: int
    node_key: str
    node_type: str
    title: str
    purpose: str
    owner: str
    execution_mode: str
    input_contract: dict[str, str]
    output_contract: dict[str, str]
    preconditions: tuple[str, ...]
    evidence_requirements: tuple[str, ...]
    reason_codes: tuple[str, ...]
    test_cases: tuple[dict[str, Any], ...]
    monitoring_metrics: tuple[str, ...]
    timeout_seconds: int | None = None
    retry_policy: dict[str, Any] | None = None
    fallback_node_key: str | None = None
    required_role: str | None = None
    financial_impact: bool = False
    legal_impact: bool = False
    model_or_policy_dependency: str | None = None

    def __post_init__(self) -> None:
        if self.node_type not in NODE_TYPES:
            raise ValueError(f"unknown node_type: {self.node_type!r}")
        if self.node_type not in ACTIVATABLE_NODE_TYPES:
            # FR-ALG-08: ml/hybrid are representable in the schema for a
            # future phase, but this task builds no compiler to gate their
            # activation -- so the model itself refuses to construct one.
            raise ValueError(
                f"node_type {self.node_type!r} is not activatable until Phase 8 (FR-ALG-08); "
                "the type exists in NODE_TYPES for future schema stability, not for use here"
            )
        if not self.node_key.strip():
            raise ValueError("node_key must be non-empty")
        if not self.title.strip():
            raise ValueError("title must be non-empty")
        if not self.owner.strip():
            raise ValueError("owner must be non-empty")


@dataclass(frozen=True)
class PolicyEdge:
    policy_version_id: int
    from_node_key: str
    to_node_key: str
    condition_label: str | None = None

    def __post_init__(self) -> None:
        if not self.from_node_key.strip() or not self.to_node_key.strip():
            raise ValueError("from_node_key/to_node_key must be non-empty")


@dataclass(frozen=True)
class PolicyVersionTransition:
    policy_version_id: int
    from_status: str
    to_status: str
    changed_by: str
    reason: str | None = field(default=None)
