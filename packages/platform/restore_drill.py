"""Restore-drill evidence (Phase 6, task 6.C, NFR-REL-01 / master plan
§23.1's "backup age / restore drill age" line): docs/operations/runbook.md's
step 3 already required a restore drill to be "performed and logged", but no
logging mechanism existed until this module -- every prior release relied on
an operator's unverifiable claim. Append-only, same discipline as
deployment_authorizations/audit_log: a bad drill result is not corrected by
editing this row, only by running and recording a new drill. Learned from
packages/platform/deployment_authorization.py's own bug fix: ORDER BY on a
`DEFAULT now()` timestamp column ties when multiple rows are written inside
one transaction (now() is transaction-start time in Postgres) -- `id DESC`
is included as a tiebreaker from the start here, not bolted on after a bug
report."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


async def record_restore_drill(
    conn: AsyncConnection,
    *,
    backup_filename: str,
    target_database: str,
    passed: bool,
    detail: str,
) -> int:
    row = (
        (
            await conn.execute(
                text(
                    """
                    INSERT INTO restore_drill_runs (backup_filename, target_database, passed, detail)
                    VALUES (:backup_filename, :target_database, :passed, :detail)
                    RETURNING id
                    """
                ),
                {
                    "backup_filename": backup_filename,
                    "target_database": target_database,
                    "passed": passed,
                    "detail": detail,
                },
            )
        )
        .mappings()
        .one()
    )
    return row["id"]


async def latest_passing_drill(conn: AsyncConnection) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, backup_filename, target_database, passed, detail, drilled_at
                    FROM restore_drill_runs
                    WHERE passed = TRUE
                    ORDER BY drilled_at DESC, id DESC
                    LIMIT 1
                    """
                )
            )
        )
        .mappings()
        .first()
    )
    return dict(row) if row is not None else None
