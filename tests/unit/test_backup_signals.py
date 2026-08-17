"""Backup-age signal (Phase 6, task 6.C, master plan §23.1's "backup age"
line). Pure filesystem scan -- no DB, no network -- so this belongs in
tests/unit/ per tests/README.md's Fast/Full split."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from packages.platform.backup_signals import latest_backup_at


def test_returns_none_when_directory_has_no_backup_files(tmp_path: Path):
    assert latest_backup_at(tmp_path) is None


def test_returns_none_when_directory_does_not_exist(tmp_path: Path):
    assert latest_backup_at(tmp_path / "does-not-exist") is None


def test_ignores_non_matching_filenames(tmp_path: Path):
    (tmp_path / "not-a-backup.txt").write_text("noise")
    (tmp_path / "backup_20260817T120000Z.dump.tmp").write_text("partial, wrong suffix")
    assert latest_backup_at(tmp_path) is None


def test_returns_the_newest_backup_timestamp(tmp_path: Path):
    (tmp_path / "backup_20260815T090000Z.dump").write_text("older")
    (tmp_path / "backup_20260817T120000Z.dump").write_text("newer")
    (tmp_path / "backup_20260816T030000Z.dump").write_text("middle")

    result = latest_backup_at(tmp_path)

    assert result == datetime(2026, 8, 17, 12, 0, 0, tzinfo=UTC)
