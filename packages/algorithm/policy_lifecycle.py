"""АЛГОРИТМ policy-version lifecycle transition graph (Phase 5, task 5.A,
docs/reports/PLAN-MISSION-5.md Section3). Pure logic, no DB.

docs/reports/PLAN-MISSION-5.md Section3 states the linear sequence "draft ->
simulation -> business_review -> risk_review -> approved -> active ->
retired" plus "rejected/suspended ветви" (branches) without naming exactly
which states branch to which. ALLOWED_TRANSITIONS below is this task's own
concrete reading of that sequence -- recorded as a deviation in
docs/decisions/OPEN-QUESTIONS.md at close-out, not spec text, and open to
revision once task 5.B/5.C's real compiler/simulation needs surface a
different shape.

IMMUTABLE_STATUSES governs CONTENT (nodes/edges), not the status column
itself -- an approved/active version can still legitimately progress
(approved->active, active->retired/suspended) without that being a content
edit. policy_store.py enforces the content half structurally (no
update/delete function exists for policy_nodes/policy_edges)."""

from __future__ import annotations

from .policy_model import IMMUTABLE_STATUSES as IMMUTABLE_STATUSES  # re-export for callers

ALLOWED_TRANSITIONS: dict[str, tuple[str, ...]] = {
    "draft": ("simulation",),
    "simulation": ("business_review", "rejected"),
    "business_review": ("risk_review", "rejected"),
    "risk_review": ("approved", "rejected"),
    "approved": ("active",),
    "active": ("retired", "suspended"),
    "suspended": ("active", "retired"),
    "retired": (),
    "rejected": (),
}


def can_transition(from_status: str, to_status: str) -> bool:
    return to_status in ALLOWED_TRANSITIONS.get(from_status, ())
