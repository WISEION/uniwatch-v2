"""Live DB invariant checks (Phase 6, task 6.B's Task 2; master plan §22
Gate 5's "DB invariants" line, NEG-06 -- green CI is not production
deployment authorization, so a post-deploy gate needs its own real check
against the actually-running database).

`packages/platform/migrations_runner.py`'s `preflight`/`postflight` hooks
(exercised by `tests/integration/test_invariant_quarantine.py`) only ever run
*during* `apply_all()` -- there was no standalone way to ask "is this
invariant still intact right now" against an already-migrated, live
database, independent of any migration being applied. This module is that:
each function is a pure, reusable, read-only check against a live
`AsyncConnection` (the same SQLAlchemy async connection every other
`packages/*_store.py` module uses -- not a raw `asyncpg.Connection` the way
`migrations_runner.py` talks to Postgres directly, which is that module's own
documented exception, not the norm here).

Each check returns an `InvariantResult`, not a bare boolean, so a failure is
actionable (which rows, how many) instead of just "false" (hard ban #3: no
silent fallback -- a state is always surfaced with enough detail to act on).

`ALL_CHECKS` is the registry `scripts/check_invariants.py` iterates; add a
new check function here and to that tuple, not by hand-rolling a one-off
query somewhere else.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class InvariantResult:
    name: str
    passed: bool
    detail: str


InvariantCheck = Callable[[AsyncConnection], Awaitable[InvariantResult]]


async def _table_exists(conn: AsyncConnection, table_name: str) -> bool:
    result = await conn.execute(text("SELECT to_regclass(:qualified) IS NOT NULL"), {"qualified": f"public.{table_name}"})
    return bool(result.scalar_one())


async def no_orphaned_notifications(conn: AsyncConnection) -> InvariantResult:
    """Re-implements, as a standalone live check, the exact FK-orphan query
    `tests/integration/test_invariant_quarantine.py`'s
    `_orphaned_user_id_count` uses (P007: "14 FK violations in a local
    snapshot" -- a preflight hook quarantines a migration that would add a
    constraint real data already violates).

    `notifications` is not part of the current production schema -- no file
    under `migrations/` creates it; it exists only as that regression test's
    own tmp-path fixture table, built to exercise the generic preflight
    mechanism against a concrete FK-orphan scenario without pre-building
    Phase 1+ domain infrastructure ahead of the plan. If/when a real
    `notifications` table is introduced, this check starts actually
    confirming the invariant against it un-modified. Until then, a schema
    that doesn't have the table yet is reported as exactly that in `detail`
    -- not silently folded into an unqualified "passed" (hard ban #3).
    """
    name = "no_orphaned_notifications"
    if not await _table_exists(conn, "notifications"):
        return InvariantResult(
            name=name,
            passed=True,
            detail=(
                "notifications table does not exist in this schema "
                "(no migration creates it yet) -- vacuously satisfied, not checked"
            ),
        )
    result = await conn.execute(
        text(
            """
            SELECT n.id, n.user_id
            FROM notifications n
            LEFT JOIN users u ON u.id = n.user_id
            WHERE u.id IS NULL
            ORDER BY n.id
            """
        )
    )
    orphans = result.mappings().all()
    if not orphans:
        return InvariantResult(name=name, passed=True, detail="no orphaned notifications.user_id rows found")
    sample = ", ".join(str(row["id"]) for row in orphans[:10])
    suffix = ", ..." if len(orphans) > 10 else ""
    return InvariantResult(
        name=name,
        passed=False,
        detail=f"{len(orphans)} notifications row(s) reference a non-existent users.id (notification id(s): {sample}{suffix})",
    )


async def policy_versions_one_active_per_graph(conn: AsyncConnection) -> InvariantResult:
    """Confirms `migrations/0019_algoritm_activation_guard.sql`'s partial
    unique index (`policy_versions_one_active_per_graph`, on
    `policy_versions (policy_graph_id) WHERE status = 'active'`) is actually
    holding on the live database.

    This is a read-only *confirmation* that the structural guarantee is
    intact, not a new rule layered on top of it: if the index is ever
    dropped, bypassed, or a restore brings back inconsistent data, this is
    the check that would catch two `active` versions of the same
    `policy_graph_id` coexisting.
    """
    name = "policy_versions_one_active_per_graph"
    result = await conn.execute(
        text(
            """
            SELECT policy_graph_id, count(*) AS active_count
            FROM policy_versions
            WHERE status = 'active'
            GROUP BY policy_graph_id
            HAVING count(*) > 1
            ORDER BY policy_graph_id
            """
        )
    )
    violations = result.mappings().all()
    if not violations:
        return InvariantResult(name=name, passed=True, detail="every policy_graph_id has at most one active policy_versions row")
    detail_parts = ", ".join(f"policy_graph_id={row['policy_graph_id']} ({row['active_count']} active)" for row in violations)
    return InvariantResult(
        name=name,
        passed=False,
        detail=f"{len(violations)} policy_graph_id(s) have more than one active version: {detail_parts}",
    )


async def no_orphaned_user_roles(conn: AsyncConnection) -> InvariantResult:
    """FK-orphan check for `migrations/0001_platform_core.sql`'s
    `users.role_id -> roles.id` relationship -- same shape as
    `no_orphaned_notifications`, but against a table that is always present
    (created unconditionally by migration 0001, unlike `notifications`).
    `users.role_id` carries a real `REFERENCES roles (id)` constraint, so an
    orphan here would mean the constraint was bypassed or dropped (e.g. a
    restore from an inconsistent backup) -- this is the live proof that
    didn't happen, the same "structural, not just checked" discipline as
    `policy_versions_one_active_per_graph` above.
    """
    name = "no_orphaned_user_roles"
    result = await conn.execute(
        text(
            """
            SELECT u.id, u.username, u.role_id
            FROM users u
            LEFT JOIN roles r ON r.id = u.role_id
            WHERE r.id IS NULL
            ORDER BY u.id
            """
        )
    )
    orphans = result.mappings().all()
    if not orphans:
        return InvariantResult(name=name, passed=True, detail="no orphaned users.role_id rows found")
    sample = ", ".join(f"{row['id']}:{row['username']}" for row in orphans[:10])
    suffix = ", ..." if len(orphans) > 10 else ""
    return InvariantResult(
        name=name,
        passed=False,
        detail=f"{len(orphans)} users row(s) reference a non-existent roles.id (id:username: {sample}{suffix})",
    )


ALL_CHECKS: tuple[InvariantCheck, ...] = (
    no_orphaned_notifications,
    policy_versions_one_active_per_graph,
    no_orphaned_user_roles,
)
