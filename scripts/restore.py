"""Restore command: thin CLI wrapper around the real `pg_restore` binary --
the inverse of `scripts/backup.py`.

Phase 6 task 6.B (`NFR-REL-01`). Does not reimplement restore logic -- shells
out to `pg_restore` against a `pg_dump -Fc` file and fails loudly: a missing
binary, a missing backup file, or a non-zero `pg_restore` exit code all raise
`RestoreError` / exit non-zero rather than leaving a silently half-restored
target database.

Same convention as `scripts/migrate.py` and `scripts/backup.py`: importable
functions first, a thin `if __name__ == "__main__":` CLI wrapper last. The
`to_libpq_dsn` helper is duplicated from `backup.py` rather than imported --
`scripts/` has no `__init__.py` (matching `migrate.py`'s existing
convention), and this script is invoked directly as `python scripts/restore.py`
(see `docker-compose.local.yml`'s `migrate` service for the sibling
`scripts/migrate.py` invocation this mirrors), which does not put the repo
root on `sys.path` the way an editable-installed package import would need.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

from packages.platform.settings import get_settings


class RestoreError(RuntimeError):
    """Raised when pg_restore cannot run or fails -- never silently swallowed."""


def to_libpq_dsn(database_url: str) -> str:
    """Strip the SQLAlchemy `+asyncpg` driver qualifier -- `pg_restore`
    speaks plain libpq connection URIs, not SQLAlchemy URLs. Same
    substitution as `Settings.asyncpg_dsn` / `backup.py`'s own helper."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def restore_backup(backup_path: Path, database_url: str) -> None:
    """Run `pg_restore` for `backup_path` into `database_url`. The target
    database must already exist (this does not create one -- creating a
    fresh restore target is the caller's decision, not something to do
    implicitly). Raises `RestoreError` if `pg_restore` isn't on PATH, the
    backup file doesn't exist, or the restore exits non-zero."""
    if not backup_path.is_file():
        raise RestoreError(f"backup file not found: {backup_path}")

    pg_restore = shutil.which("pg_restore")
    if pg_restore is None:
        raise RestoreError("pg_restore not found on PATH -- install the PostgreSQL client tools (postgresql-client)")

    dsn = to_libpq_dsn(database_url)
    result = subprocess.run(
        [pg_restore, "--no-owner", "--no-privileges", "-d", dsn, str(backup_path)],
        capture_output=True,
        text=True,
        # Without an explicit stdin redirect, pg_restore inherits the
        # caller's stdin and can block indefinitely (e.g. on a libpq
        # password prompt) instead of failing fast -- the whole point of
        # this module's fail-loud contract.
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise RestoreError(f"pg_restore failed (exit {result.returncode}): {result.stderr.strip()}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Restore a UNIWatch database backup via pg_restore.")
    parser.add_argument("backup_file", help="Path to a .dump file produced by scripts/backup.py")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy-style DATABASE_URL to restore into (default: $DATABASE_URL env var, "
        "then packages/platform/settings.py's dev default)",
    )
    args = parser.parse_args(argv)

    database_url = args.database_url or os.environ.get("DATABASE_URL") or get_settings().database_url

    try:
        restore_backup(Path(args.backup_file), database_url)
    except RestoreError as exc:
        print(f"restore failed: {exc}", file=sys.stderr)
        return 1

    print(f"restored {args.backup_file}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
