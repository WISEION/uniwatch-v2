"""FR-MIG-04, NEG-01, NEG-02: the v1-untouched gate reports what it could
not read. A file it cannot scan is a file it cannot clear, so it must never
be skipped into a pass."""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

# `tools/` is a CI-script directory, not an installed package (see AGENTS.md
# §5) — loaded by path rather than made importable just for this test.
_spec = importlib.util.spec_from_file_location(
    "check_v1_untouched",
    Path(__file__).resolve().parents[2] / "tools" / "check_v1_untouched.py",
)
assert _spec is not None and _spec.loader is not None
check_v1_untouched = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(check_v1_untouched)


def test_unreadable_repo_file_is_reported_as_a_violation(tmp_path, monkeypatch):
    unreadable = tmp_path / "sneaky.cfg"
    unreadable.write_text("harmless", encoding="utf-8")
    monkeypatch.setattr(check_v1_untouched, "REPO_ROOT", tmp_path)

    original_read_text = type(unreadable).read_text

    def deny_read(self, *args, **kwargs):
        if self.name == "sneaky.cfg":
            raise PermissionError(13, "Permission denied")
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(type(unreadable), "read_text", deny_read)

    violations = check_v1_untouched.scan_for_literals()

    assert len(violations) == 1
    assert "sneaky.cfg" in violations[0]
    assert "could not be scanned" in violations[0]


def test_unhashable_v1_file_fails_the_baseline_check_instead_of_being_dropped(tmp_path, monkeypatch):
    v1_path = tmp_path / "v1"
    v1_path.mkdir()
    (v1_path / "a.txt").write_text("a", encoding="utf-8")

    monkeypatch.setattr(check_v1_untouched, "V1_PATHS", [v1_path])
    monkeypatch.setattr(check_v1_untouched, "BASELINE_FILE", tmp_path / "baseline.json")
    monkeypatch.setattr(
        check_v1_untouched,
        "hash_file",
        lambda path: (_ for _ in ()).throw(PermissionError(13, "Permission denied")),
    )

    with pytest.raises(check_v1_untouched.UnreadableV1File):
        check_v1_untouched.snapshot(v1_path)

    problems = check_v1_untouched.check_baseline(init=False)

    assert len(problems) == 1
    assert "could not hash" in problems[0]
