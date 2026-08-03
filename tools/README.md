# tools/

Repo-hygiene tools, invoked from `.ci/` gates. Stdlib-only (no dependencies) so they can run before 0.B introduces a package manager.

- `check_v1_untouched.py` — FR-MIG-04 / NEG-01 / NEG-02: fails if a v1 path literal appears outside the doc allowlist, or if the recorded v1 baseline (`v1-baseline.json`) shows drift. See `.ci/README.md`.
