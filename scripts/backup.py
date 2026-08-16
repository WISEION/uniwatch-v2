"""Backup command: thin CLI wrapper around the real `pg_dump` binary.

Phase 6 task 6.B (`NFR-REL-01`, master plan §22 Gate 3's "backup/restore
drill"). This deliberately does not reimplement dump logic -- it shells out
to `pg_dump -Fc` (custom format, required for `pg_restore` to later be
selective/parallel) and fails loudly on any error: missing binary, bad
connection, or a non-zero `pg_dump` exit code all raise `BackupError` /exit
non-zero rather than silently producing an empty or partial file.

Same convention as `scripts/migrate.py`: importable functions first, a thin
`if __name__ == "__main__":` CLI wrapper last, no package structure
(`scripts/` has no `__init__.py`, same as `migrate.py`).
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path

from packages.platform.settings import get_settings


class BackupError(RuntimeError):
    """Raised when pg_dump cannot run or fails -- never silently swallowed."""


def to_libpq_dsn(database_url: str) -> str:
    """Strip the SQLAlchemy `+asyncpg` driver qualifier -- `pg_dump` speaks
    plain libpq connection URIs, not SQLAlchemy URLs. Same substitution as
    `Settings.asyncpg_dsn`."""
    return database_url.replace("postgresql+asyncpg://", "postgresql://", 1)


def build_backup_filename(now: datetime | None = None) -> str:
    """`backup_<ISO8601>.dump`, using ISO 8601's basic (no-separator) form
    (`YYYYMMDDTHHMMSSZ`) so the filename stays valid on Windows, where `:`
    is illegal in a path component."""
    timestamp = (now or datetime.now(UTC)).strftime("%Y%m%dT%H%M%SZ")
    return f"backup_{timestamp}.dump"


def create_backup(database_url: str, output_dir: Path, *, filename: str | None = None) -> Path:
    """Run `pg_dump -Fc` against `database_url`, writing the result under
    `output_dir`. Returns the path written. Raises `BackupError` -- never
    returns a partial/empty file silently -- if `pg_dump` isn't on PATH or
    exits non-zero (bad connection, auth failure, etc.)."""
    pg_dump = shutil.which("pg_dump")
    if pg_dump is None:
        raise BackupError("pg_dump not found on PATH -- install the PostgreSQL client tools (postgresql-client)")

    output_dir.mkdir(parents=True, exist_ok=True)
    dest = output_dir / (filename or build_backup_filename())
    dsn = to_libpq_dsn(database_url)

    result = subprocess.run(
        [pg_dump, "-Fc", "-f", str(dest), dsn],
        capture_output=True,
        text=True,
        # Without an explicit stdin redirect, pg_dump inherits the caller's
        # stdin and can block indefinitely (e.g. on a libpq password prompt)
        # instead of failing fast -- the whole point of this module's
        # fail-loud contract.
        stdin=subprocess.DEVNULL,
    )
    if result.returncode != 0:
        raise BackupError(f"pg_dump failed (exit {result.returncode}): {result.stderr.strip()}")
    return dest


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Back up a UNIWatch database via pg_dump (custom format).")
    parser.add_argument(
        "--database-url",
        default=None,
        help="SQLAlchemy-style DATABASE_URL (default: $DATABASE_URL env var, then packages/platform/settings.py's dev default)",
    )
    parser.add_argument(
        "--output-dir",
        default="./backups",
        help="Directory to write the timestamped .dump file into (default: ./backups/)",
    )
    args = parser.parse_args(argv)

    database_url = args.database_url or os.environ.get("DATABASE_URL") or get_settings().database_url

    try:
        dest = create_backup(database_url, Path(args.output_dir))
    except BackupError as exc:
        print(f"backup failed: {exc}", file=sys.stderr)
        return 1

    print(f"wrote {dest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
