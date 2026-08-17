"""Executes a real restore drill (Phase 6, task 6.C, NFR-REL-01):
backs up `--source-database-url`, restores it into `--drill-database-url`
(a scratch database -- never the source or a production target; restoring
overwrites whatever the drill database currently holds), and records the
result in the SOURCE database via packages/platform/restore_drill.py --
not the drill database, since pg_restore replaces that database's entire
contents on the next run, which would erase its own evidence row.
docs/operations/runbook.md's step 3 (previously an unverifiable claim) reads
this table's latest passing row. Exits non-zero on any failure; a failed
drill is exactly the fact this script exists to catch, so it records a
`passed=False` row (never silently skips recording) before exiting non-zero.
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from packages.platform.db import connection_scope, get_engine
from packages.platform.restore_drill import record_restore_drill
from scripts.backup import BackupError, create_backup
from scripts.restore import RestoreError, restore_backup


async def run_drill(*, source_database_url: str, drill_database_url: str, backup_dir: Path) -> int:
    passed = True
    detail = ""
    backup_filename = ""

    try:
        backup_path = create_backup(source_database_url, backup_dir)
        backup_filename = backup_path.name
    except BackupError as exc:
        passed = False
        detail = str(exc)
        # Use a placeholder filename when backup fails -- not a fake real filename
        backup_filename = "(backup failed)"
    else:
        # Only attempt restore if backup succeeded
        detail = f"restored {backup_filename} into drill target successfully"
        try:
            restore_backup(backup_path, drill_database_url)
        except RestoreError as exc:
            passed = False
            detail = str(exc)

    engine = get_engine(source_database_url)
    try:
        async with connection_scope(engine) as conn:
            await record_restore_drill(
                conn,
                backup_filename=backup_filename,
                target_database=drill_database_url,
                passed=passed,
                detail=detail,
            )
    finally:
        await engine.dispose()

    if not passed:
        print(f"[FAIL] restore drill: {detail}")
        return 1
    print(f"[PASS] restore drill: {detail}")
    return 0


async def _main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run and record a UNIWatch v2 restore drill.")
    parser.add_argument("--source-database-url", required=True, help="the environment being certified as restorable")
    parser.add_argument("--drill-database-url", required=True, help="scratch database the backup is restored into")
    parser.add_argument("--backup-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    return await run_drill(
        source_database_url=args.source_database_url,
        drill_database_url=args.drill_database_url,
        backup_dir=args.backup_dir,
    )


def main(argv: list[str] | None = None) -> int:
    return asyncio.run(_main(argv))


if __name__ == "__main__":
    sys.exit(main())
