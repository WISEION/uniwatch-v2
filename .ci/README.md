# .ci/

CI gate definitions. The actual CI runner/workflow engine is wired up in task 0.D (qa): `.github/workflows/ci.yml` — Fast gate (v1-untouched, format/lint/typecheck, unit tests, OpenAPI schema build, migration-file syntax) and Full gate (the full `tests/` suite, currently unit+integration; contract/state/security/e2e/performance grow as Phase 1+ adds tests to those suites, per `tests/README.md`), per `docs/reports/PLAN-MISSION-1.md` §2. GitHub Actions is an implementation choice recorded in `docs/decisions/OPEN-QUESTIONS.md` (2026-08-04 — CI runner platform), not a locked decision from the source docs.

Migration rehearsal (empty + seeded DB, idempotent repeat, FR-PLT-12), the invariant-quarantine test (FR-PLT-13, P007), and the worker-restart-resume test (FR-JOB-03) are covered by existing tests under `tests/integration/` (`test_migrations_runner.py`, `test_invariant_quarantine.py`, `test_jobs_store.py`) and run as part of the Full gate above — no separate CI step is needed for them.

## Gates defined so far (0.A)

| Gate | Check | Script | Requirement |
|---|---|---|---|
| Fast (blocking, every commit) | v1 untouched: no forbidden path literal outside `docs/`/`AGENTS.md`/`README.md`/`_supervisor/`; no drift from the recorded v1 baseline | `python tools/check_v1_untouched.py` | FR-MIG-04, NEG-01, NEG-02 |

Run locally: `python tools/check_v1_untouched.py` (first time on a machine where v1 is present: `python tools/check_v1_untouched.py --init` to record the baseline in `tools/v1-baseline.json`).

This check has no third-party dependencies (Python stdlib only) — it can run before any package manager/dependency is introduced in 0.B.

## Security gate — stub plan (0.C)

`NFR-SEC-07` (dependency/secret/license scanning) and `NFR-SEC-09` (image digest integrity) require CI checks that are not wired yet — no CI runner exists until 0.D. This section is the plan those checks are wired against; it names candidate tool categories, not locked-in tool choices (no new dev dependency has been added for this yet — that is a 0.D decision, made when the check is actually wired, same discipline as the migration-runner-tool choice in `migrations/README.md`).

| Check | Purpose | Candidate approach | When it blocks |
|---|---|---|---|
| Secret scan | Catch a committed credential/token before it reaches history | A git-history-aware scanner (e.g. gitleaks/trufflehog-class tool) run on the diff for every PR | Fast gate, every commit, once wired in 0.D |
| Dependency scan (SCA) | Catch a known-vulnerable pinned dependency (`pyproject.toml` pins every version already — §"Commands" in `CLAUDE.md` — so a scan has a fixed target to check) | A Python-ecosystem SCA tool (e.g. pip-audit/osv-scanner-class tool) against the resolved dependency set | Full gate initially; promoted to a Fast-gate blocker once the baseline is clean, per NIST SSDF practice referenced in the threat model (T6) |
| License scan | Catch a dependency whose license is incompatible with distribution/use | A license-listing tool (e.g. pip-licenses-class tool) with an explicit allow-list of acceptable licenses | Release-candidate gate (not Phase 0/1) — full enforcement is later per `docs/architecture/threat-model.md` T6 |
| Image digest integrity | A deployed artifact must match the exact commit that was reviewed (v1 RN-11/RN-12 failure mode: tag drift) | Immutable image digest recorded at build, checked at production authorization against the reviewing commit | Production-authorization gate (`INV-14`), Phase 6 — no build/deploy pipeline exists yet |

None of the above is implemented in this task (0.C) — this table is the plan `0.D` wires against, per `docs/reports/PLAN-MISSION-1.md` §2 ("CI security-gate stub ... план"). Full inclusion criteria and tool selection are recorded here (not silently decided) the moment 0.D actually adds the dependency and the workflow step.

Everything else in the Fast/Full gate table (`docs/reports/PLAN-MISSION-1.md` §2, 0.D) is not wired yet — this file is extended, not replaced, when 0.D starts.
