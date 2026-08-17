"""Deployment authorization CLI (Phase 6, task 6.B, Gate 4 -- FR-AUT-06/
INV-14). The command a human approver actually runs before a production
deployment. Refuses (non-zero exit, no DB write) if the approver is not
distinct from the initiator, or the release manifest's commit doesn't
match the commit being authorized -- this is the first mechanical
enforcement of docs/adr/0005-authority-model.md's distinct-approver rule
anywhere in this repo; every prior deployment's distinct-approver fact was
a manually-asserted WORKLOG.md note, not something this checked.

Usage:
    python scripts/authorize_deployment.py <pr_number> --approver <github-login> \\
        [--manifest release-manifest.json] [--repo owner/repo] [--notes "..."]

The initiator is read from the PR itself (gh api's user.login) -- not
supplied by the caller, so the check can't be defeated by simply passing
whatever value happens to differ from --approver.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import subprocess
import sys
from pathlib import Path

from packages.platform.db import get_engine
from packages.platform.deployment_authorization import (
    record_authorization,
    verify_digest_match,
    verify_distinct_approver,
)
from packages.platform.migrations_runner import MigrationRunner
from packages.platform.settings import get_settings

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


class AuthorizationRefused(Exception):
    pass


def fetch_pr_info(pr_number: int, repo: str) -> dict[str, str]:
    result = subprocess.run(
        ["gh", "api", f"repos/{repo}/pulls/{pr_number}"],
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    initiator = payload["user"]["login"]
    # The PR's head commit, not merge_commit_sha: CI builds the candidate
    # image from the branch's own head commit, before any merge commit
    # exists -- that's the commit the release manifest actually recorded
    # (once ci.yml's build-images job uses the real PR head sha rather
    # than a pull_request-triggered run's ephemeral github.sha, which is a
    # GitHub-internal test-merge commit that never persists in history).
    commit_sha = payload["head"]["sha"]
    return {"initiator": initiator, "commit_sha": commit_sha}


def load_manifest(path: Path) -> dict:
    if not path.exists():
        raise AuthorizationRefused(f"release manifest not found: {path}")
    return json.loads(path.read_text(encoding="utf-8"))


async def authorize(
    *,
    pr_number: int,
    approver: str,
    repo: str,
    manifest_path: Path,
    notes: str | None,
) -> int:
    pr_info = fetch_pr_info(pr_number, repo)
    initiator = pr_info["initiator"]
    commit_sha = pr_info["commit_sha"]

    if not verify_distinct_approver(initiator, approver):
        raise AuthorizationRefused(
            f"approver ({approver!r}) must be distinct from the initiator ({initiator!r}) -- FR-AUT-06/INV-14"
        )

    manifest = load_manifest(manifest_path)
    if not verify_digest_match(manifest, commit_sha):
        raise AuthorizationRefused(
            f"release manifest's commit_sha ({manifest.get('commit_sha')!r}) "
            f"does not match PR #{pr_number}'s commit ({commit_sha!r})"
        )

    settings = get_settings()
    runner = MigrationRunner(settings.asyncpg_dsn, MIGRATIONS_DIR)
    current_version = await runner.current_version()
    if current_version != settings.expected_schema_version:
        raise AuthorizationRefused(
            f"DB schema version mismatch: target DB is at {current_version}, "
            f"this codebase expects {settings.expected_schema_version}"
        )

    engine = None
    try:
        engine = get_engine(settings.database_url)
        async with engine.begin() as conn:
            authorization_id = await record_authorization(
                conn,
                commit_sha=commit_sha,
                image_digests=manifest.get("images", {}),
                initiator=initiator,
                approver=approver,
                db_schema_version_at_authorization=current_version,
                notes=notes,
            )
    finally:
        if engine is not None:
            await engine.dispose()

    return authorization_id


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("pr_number", type=int)
    parser.add_argument("--approver", required=True, help="GitHub login of the approving identity")
    parser.add_argument("--repo", default="WISEION/uniwatch-v2")
    parser.add_argument("--manifest", type=Path, default=Path("release-manifest.json"))
    parser.add_argument("--notes", default=None)
    args = parser.parse_args()

    try:
        authorization_id = asyncio.run(
            authorize(
                pr_number=args.pr_number,
                approver=args.approver,
                repo=args.repo,
                manifest_path=args.manifest,
                notes=args.notes,
            )
        )
    except AuthorizationRefused as exc:
        print(f"DEPLOYMENT AUTHORIZATION REFUSED: {exc}", file=sys.stderr)
        sys.exit(1)

    print(f"deployment authorized: id={authorization_id}")


if __name__ == "__main__":
    main()
