"""Pure backup-age signal (Phase 6, task 6.C, master plan §23.1's "backup
age" line). scripts/backup.py writes files named by its own
build_backup_filename() -- backup_<UTC timestamp>.dump -- and persists no DB
row (unlike a restore drill, a backup is not something later code needs to
query relationally; only "how old is the newest one" matters here). No new
table, just a filesystem scan; an empty/missing directory is a real,
surfaced state (None), never treated as "age zero" (hard ban #3)."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

_BACKUP_FILENAME_PREFIX = "backup_"
_BACKUP_FILENAME_SUFFIX = ".dump"
_BACKUP_TIMESTAMP_FORMAT = "%Y%m%dT%H%M%SZ"


def latest_backup_at(backup_dir: Path) -> datetime | None:
    """Parses the UTC timestamp out of every `backup_<ts>.dump` filename in
    `backup_dir` (matching scripts/backup.py::build_backup_filename's exact
    format) and returns the newest, or None if the directory holds no
    matching file or does not exist. Reads the filename, not the file's
    mtime, so a copied/moved backup file (mtime reset by the copy) still
    reports its real backup time."""
    if not backup_dir.is_dir():
        return None

    newest: datetime | None = None
    for path in backup_dir.iterdir():
        if not (path.name.startswith(_BACKUP_FILENAME_PREFIX) and path.name.endswith(_BACKUP_FILENAME_SUFFIX)):
            continue
        timestamp_str = path.name[len(_BACKUP_FILENAME_PREFIX) : -len(_BACKUP_FILENAME_SUFFIX)]
        try:
            parsed = datetime.strptime(timestamp_str, _BACKUP_TIMESTAMP_FORMAT).replace(tzinfo=UTC)
        except ValueError:
            continue
        if newest is None or parsed > newest:
            newest = parsed
    return newest
