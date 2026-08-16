"""Deployment authorization (Phase 6, task 6.B, Gate 4 -- FR-AUT-06/INV-14,
`docs/adr/0005-authority-model.md`): "production deployment requires a
distinct approver from the initiator" had zero mechanical enforcement
before this task -- the repo's own GitHub ruleset only requires the
Fast/Full gate status checks, no required-reviewer rule, so every prior
PR's distinct-approver fact was a manually-asserted `WORKLOG.md` note, not
something CI or GitHub verified. `verify_distinct_approver`/
`verify_digest_match` are the actual checks; `record_authorization` is the
append-only evidence a check passed. No update/delete function exists for
`deployment_authorizations` -- a wrong authorization is corrected by a new
row, not by editing history, same as `audit_log`."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def verify_distinct_approver(initiator: str, approver: str) -> bool:
    """FR-AUT-06/INV-14's actual rule: the identity approving a deployment
    must not be the identity that initiated it. Case-sensitive exact match
    on the identity string (a GitHub login, e.g. `gh api`'s `user.login`/
    `merged_by.login`) -- no fuzzy/normalized comparison, since a login is
    already a canonical identifier."""
    return initiator != approver


def verify_digest_match(manifest: dict[str, Any], commit_sha: str) -> bool:
    """Confirms the release manifest (`docs/operations/release-manifest.md`'s
    shape: `{"commit_sha": ..., "images": {...}, "built_at": ...}`) was
    actually built from the commit being authorized -- guards against the
    v1 RN-11/RN-12 failure mode of a deployed artifact drifting from the
    reviewed commit. Does not re-verify the digests themselves against a
    registry (there is none, D-HOST is local-network-only) -- only that
    this manifest's own recorded commit matches."""
    return manifest.get("commit_sha") == commit_sha


async def record_authorization(
    conn: AsyncConnection,
    *,
    commit_sha: str,
    image_digests: dict[str, str],
    initiator: str,
    approver: str,
    db_schema_version_at_authorization: int,
    notes: str | None = None,
) -> int:
    row = (
        (
            await conn.execute(
                text(
                    """
                    INSERT INTO deployment_authorizations
                        (commit_sha, image_digests, initiator, approver,
                         db_schema_version_at_authorization, notes)
                    VALUES (:commit_sha, CAST(:image_digests AS jsonb), :initiator, :approver,
                            :db_schema_version_at_authorization, :notes)
                    RETURNING id
                    """
                ),
                {
                    "commit_sha": commit_sha,
                    "image_digests": json.dumps(image_digests),
                    "initiator": initiator,
                    "approver": approver,
                    "db_schema_version_at_authorization": db_schema_version_at_authorization,
                    "notes": notes,
                },
            )
        )
        .mappings()
        .one()
    )
    return row["id"]


async def get_authorization(conn: AsyncConnection, authorization_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, commit_sha, image_digests, initiator, approver,
                           db_schema_version_at_authorization, authorized_at, notes
                    FROM deployment_authorizations
                    WHERE id = :id
                    """
                ),
                {"id": authorization_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    result = dict(row)
    result["image_digests"] = json.loads(result["image_digests"])
    return result


async def latest_authorization_for_commit(conn: AsyncConnection, commit_sha: str) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, commit_sha, image_digests, initiator, approver,
                           db_schema_version_at_authorization, authorized_at, notes
                    FROM deployment_authorizations
                    WHERE commit_sha = :commit_sha
                    ORDER BY authorized_at DESC
                    LIMIT 1
                    """
                ),
                {"commit_sha": commit_sha},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        return None
    result = dict(row)
    result["image_digests"] = json.loads(result["image_digests"])
    return result
