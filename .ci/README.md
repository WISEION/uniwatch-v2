# .ci/

CI gate definitions. The actual CI runner/workflow engine is wired up in task 0.D (qa) — Fast gate (format/lint/typecheck/unit/schema/migration-syntax) and Full gate (integration/contract/state/security/e2e/migration-rehearsal/invariant-check), per `docs/reports/PLAN-MISSION-1.md` §2.

## Gates defined so far (0.A)

| Gate | Check | Script | Requirement |
|---|---|---|---|
| Fast (blocking, every commit) | v1 untouched: no forbidden path literal outside `docs/`/`AGENTS.md`/`README.md`/`_supervisor/`; no drift from the recorded v1 baseline | `python tools/check_v1_untouched.py` | FR-MIG-04, NEG-01, NEG-02 |

Run locally: `python tools/check_v1_untouched.py` (first time on a machine where v1 is present: `python tools/check_v1_untouched.py --init` to record the baseline in `tools/v1-baseline.json`).

This check has no third-party dependencies (Python stdlib only) — it can run before any package manager/dependency is introduced in 0.B.

Everything else in the Fast/Full gate table (`docs/reports/PLAN-MISSION-1.md` §2, 0.D) is not wired yet — this file is extended, not replaced, when 0.D starts.
