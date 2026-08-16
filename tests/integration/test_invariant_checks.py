"""Live DB invariant checks (Phase 6, task 6.B's Task 2; master plan §22
Gate 5's "DB invariants" line, NEG-06).

Belongs under `tests/integration/` per `tests/README.md`'s Fast/Full split:
every check in `packages/platform/invariant_checks.py` needs a real
Postgres connection (`engine` fixture -- session-scoped container, fresh
migrated `public` schema per test, from `tests/conftest.py`), so none of
this is pure logic eligible for `tests/unit/`.

Each check is proven against both a healthy state (passes) and a
deliberately-broken one (a seeded bad row the check must actually catch) --
a check that can't be shown to fail on bad data isn't proven at all.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text

from packages.platform.invariant_checks import (
    no_orphaned_notifications,
    no_orphaned_user_roles,
    policy_versions_one_active_per_graph,
)


async def test_no_orphaned_notifications_passes_when_table_absent(engine):
    # The real (non-test) migrations dir never creates a `notifications`
    # table -- it exists only as tests/integration/test_invariant_quarantine.py's
    # own tmp-path fixture. A freshly migrated schema must report this
    # honestly (vacuously satisfied), not crash or silently claim a real check ran.
    async with engine.begin() as conn:
        result = await no_orphaned_notifications(conn)
    assert result.passed is True
    assert result.name == "no_orphaned_notifications"
    assert "does not exist" in result.detail


async def test_no_orphaned_notifications_catches_seeded_orphan(engine):
    async with engine.begin() as conn:
        # Same shape as test_invariant_quarantine.py's Stage 1: a
        # notifications table with no FK constraint yet, so a row
        # referencing a non-existent user can be inserted directly.
        await conn.execute(
            text(
                """
                CREATE TABLE notifications (
                    id BIGSERIAL PRIMARY KEY,
                    user_id BIGINT NOT NULL,
                    message TEXT NOT NULL
                )
                """
            )
        )
        await conn.execute(text("INSERT INTO notifications (user_id, message) VALUES (999999, 'orphaned')"))

        result = await no_orphaned_notifications(conn)

    assert result.passed is False
    assert result.name == "no_orphaned_notifications"
    assert "1 notifications row" in result.detail


async def test_policy_versions_one_active_per_graph_passes_on_healthy_state(engine):
    async with engine.begin() as conn:
        graph_id = (
            await conn.execute(text("INSERT INTO policy_graphs (name, owner) VALUES ('healthy graph', 'tester') RETURNING id"))
        ).scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO policy_versions (policy_graph_id, version_number, status, created_by)
                VALUES (:graph_id, 1, 'active', 'tester')
                """
            ),
            {"graph_id": graph_id},
        )

        result = await policy_versions_one_active_per_graph(conn)

    assert result.passed is True
    assert result.name == "policy_versions_one_active_per_graph"


async def test_policy_versions_one_active_per_graph_catches_bypassed_structural_guard(engine):
    async with engine.begin() as conn:
        graph_id = (
            await conn.execute(text("INSERT INTO policy_graphs (name, owner) VALUES ('broken graph', 'tester') RETURNING id"))
        ).scalar_one()

        # migrations/0019_algoritm_activation_guard.sql's partial unique
        # index is the actual enforcement -- drop it to simulate the
        # structural guard having been bypassed/lost (e.g. a restore from
        # an inconsistent backup), which is exactly the scenario this check
        # exists to catch.
        await conn.execute(text("DROP INDEX policy_versions_one_active_per_graph"))
        await conn.execute(
            text(
                """
                INSERT INTO policy_versions (policy_graph_id, version_number, status, created_by)
                VALUES (:graph_id, 1, 'active', 'tester'), (:graph_id, 2, 'active', 'tester')
                """
            ),
            {"graph_id": graph_id},
        )

        result = await policy_versions_one_active_per_graph(conn)

    assert result.passed is False
    assert result.name == "policy_versions_one_active_per_graph"
    assert f"policy_graph_id={graph_id}" in result.detail
    assert "2 active" in result.detail


async def test_no_orphaned_user_roles_passes_on_healthy_state(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('bid_manager') RETURNING id"))).scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO users (username, display_name, role_id)
                VALUES ('alice', 'Alice', :role_id)
                """
            ),
            {"role_id": role_id},
        )

        result = await no_orphaned_user_roles(conn)

    assert result.passed is True
    assert result.name == "no_orphaned_user_roles"


async def test_no_orphaned_user_roles_catches_seeded_orphan(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('temp_role') RETURNING id"))).scalar_one()
        await conn.execute(
            text(
                """
                INSERT INTO users (username, display_name, role_id)
                VALUES ('bob', 'Bob', :role_id)
                """
            ),
            {"role_id": role_id},
        )

        # migrations/0001_platform_core.sql's users.role_id -> roles.id FK
        # would normally reject deleting a referenced role -- look up the
        # real constraint name (rather than assuming Postgres's default
        # naming convention) and drop it, to simulate the constraint having
        # been bypassed/lost, then remove the role out from under the user.
        constraint_name = (
            await conn.execute(
                text(
                    """
                    SELECT conname FROM pg_constraint
                    WHERE conrelid = 'users'::regclass
                      AND contype = 'f'
                      AND confrelid = 'roles'::regclass
                    """
                )
            )
        ).scalar_one()
        await conn.execute(text(f'ALTER TABLE users DROP CONSTRAINT "{constraint_name}"'))
        await conn.execute(text("DELETE FROM roles WHERE id = :role_id"), {"role_id": role_id})

        result = await no_orphaned_user_roles(conn)

    assert result.passed is False
    assert result.name == "no_orphaned_user_roles"
    assert "1 users row" in result.detail
    assert "bob" in result.detail


@pytest.mark.parametrize(
    "check",
    [no_orphaned_notifications, policy_versions_one_active_per_graph, no_orphaned_user_roles],
)
async def test_each_check_is_independently_callable_against_a_bare_connection(engine, check):
    """Each function only needs a live AsyncConnection -- no shared registry
    state, no ordering dependency between checks (FR-PLT-13-adjacent: a
    Gate-5 runner must be able to call any subset independently)."""
    async with engine.begin() as conn:
        result = await check(conn)
    assert isinstance(result.passed, bool)
    assert result.name
    assert result.detail
