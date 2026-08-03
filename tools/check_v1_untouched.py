#!/usr/bin/env python3
"""CI check: v1 is never touched by v2 (FR-MIG-04, NEG-01, NEG-02).

Two independent checks, both must pass:

1. Path-literal scan: no file in the v2 runtime/config/test/migration tree
   (i.e. anything that is not documentation) contains a literal reference to
   a v1 path. Referencing a v1 path from runtime code/config is exactly how
   a write-credential to v1 would sneak in.
2. Baseline scan (defense in depth, best-effort): if the v1 paths are present
   on the machine running this check, their file contents must be byte-for-byte
   identical to the last recorded baseline. Run with --init once, on a machine
   where v1 is present and known-untouched, to (re)create the baseline; every
   later run compares against it and fails on any added/removed/changed file.
   If v1 is not present on this machine (e.g. an isolated CI runner), this
   check is skipped with a warning, not a hard failure -- the path-literal
   scan is the primary, always-applicable guard.

Stdlib only. No third-party dependencies (0.A boundary: no dependencies added
yet in this repo).
"""

import hashlib
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent

# Protected v1 locations (kickoff TZ hard ban #1; NEG-01, NEG-02).
# Never add UNIWatch-v2 (this repo) here.
V1_PATHS = [
    Path.home() / "Documents" / "Tendet Watcher",
    Path.home() / "Documents" / "UNIWatch",
]

BASELINE_FILE = REPO_ROOT / "tools" / "v1-baseline.json"

# Literal strings that must never appear outside the allowlist below.
FORBIDDEN_LITERALS = [
    "Tendet Watcher",
    "Documents\\UNIWatch\\",
    "Documents/UNIWatch/",
]

# Files/dirs allowed to mention v1 paths in prose (documentation, this checker
# itself, and the supervisor's own task notes) -- relative to REPO_ROOT.
ALLOWLIST_PATHS = {
    "AGENTS.md",
    "README.md",
    "tools/check_v1_untouched.py",
    "tools/v1-baseline.json",
}
ALLOWLIST_DIRS = {
    "docs",
    "_supervisor",
    ".git",
}

# Directories never scanned regardless (build artifacts, VCS metadata).
SKIP_DIRS = {".git", "node_modules", "__pycache__", ".venv", "venv"}


def is_allowlisted(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT)
    rel_str = str(rel).replace("\\", "/")
    if rel_str in ALLOWLIST_PATHS:
        return True
    return any(rel_str == d or rel_str.startswith(d + "/") for d in ALLOWLIST_DIRS)


def scan_for_literals() -> list[str]:
    violations = []
    for dirpath, dirnames, filenames in os.walk(REPO_ROOT):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            path = Path(dirpath) / filename
            if is_allowlisted(path):
                continue
            try:
                text = path.read_text(encoding="utf-8", errors="ignore")
            except (UnicodeDecodeError, OSError):
                continue
            for literal in FORBIDDEN_LITERALS:
                if literal in text:
                    violations.append(
                        f"{path.relative_to(REPO_ROOT)}: contains forbidden v1 path literal '{literal}'"
                    )
    return violations


def hash_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return h.hexdigest()


def snapshot(v1_path: Path) -> dict:
    snap = {}
    for dirpath, dirnames, filenames in os.walk(v1_path):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS]
        for filename in filenames:
            p = Path(dirpath) / filename
            rel = str(p.relative_to(v1_path))
            snap[rel] = hash_file(p)
    return snap


def load_baseline() -> dict:
    if not BASELINE_FILE.exists():
        return {}
    return json.loads(BASELINE_FILE.read_text(encoding="utf-8"))


def save_baseline(baseline: dict) -> None:
    BASELINE_FILE.parent.mkdir(parents=True, exist_ok=True)
    BASELINE_FILE.write_text(json.dumps(baseline, indent=2, sort_keys=True), encoding="utf-8")


def check_baseline(init: bool) -> list[str]:
    problems = []
    baseline = load_baseline()
    changed = False

    for v1_path in V1_PATHS:
        key = str(v1_path)
        if not v1_path.exists():
            print(f"[warn] v1 path not present on this machine, skipping baseline check: {v1_path}")
            continue

        current = snapshot(v1_path)

        if init or key not in baseline:
            baseline[key] = current
            changed = True
            print(f"[init] recorded baseline for {v1_path} ({len(current)} files)")
            continue

        recorded = baseline[key]
        added = set(current) - set(recorded)
        removed = set(recorded) - set(current)
        modified = {
            f for f in (set(current) & set(recorded)) if current[f] != recorded[f]
        }

        if added:
            problems.append(f"{v1_path}: new file(s) since baseline: {sorted(added)}")
        if removed:
            problems.append(f"{v1_path}: file(s) removed since baseline: {sorted(removed)}")
        if modified:
            problems.append(f"{v1_path}: file(s) modified since baseline: {sorted(modified)}")

    if changed:
        save_baseline(baseline)

    return problems


def main() -> int:
    init = "--init" in sys.argv

    literal_violations = scan_for_literals()
    baseline_problems = check_baseline(init)

    ok = True
    if literal_violations:
        ok = False
        print("\nFAIL: v1 path literals found outside the documentation allowlist (FR-MIG-04, NEG-01, NEG-02):")
        for v in literal_violations:
            print(f"  - {v}")

    if baseline_problems:
        ok = False
        print("\nFAIL: v1 path(s) changed since baseline (FR-MIG-04):")
        for p in baseline_problems:
            print(f"  - {p}")

    if ok:
        print("PASS: v1 untouched (no forbidden path literals, no baseline drift).")
        return 0

    return 1


if __name__ == "__main__":
    raise SystemExit(main())
