# Phase 5, Task 5.E — АЛГОРИТМ: security/qa exit-gate suite — Implementation Plan

> **For agentic workers:** executed inline, same session. No subagent handoff.

**Goal:** `PLAN-MISSION-5.md` §3 task 5.E — the last task of Phase 5, closing the phase's exit gate (§5).
Unlike 5.A-5.D, this task is mostly **evidence consolidation**: 5.A/5.B/5.C/5.D's own tests already prove
most of §5's criteria as a side effect of building the mechanism. This task (1) confirms that precisely,
(2) fills the two real gaps that precedent left (a rollback rehearsal that only proved a status flip, not
restored *behavior*; a kill-switch rehearsal that never proved prior journal entries survive), and (3) adds
the one criterion nothing built before this task could satisfy at all — an automated accessibility scan of
5.D's UI (5.D's own plan explicitly deferred this: "a real automated accessibility scanner pass is 5.E's
job").

**Evidence audit against `PLAN-MISSION-5.md` §5 (before writing new code):**

| Criterion | Already covered? | Where |
|---|---|---|
| Active/approved version immutable | Yes | `tests/integration/test_policy_store.py::test_approved_version_content_is_immutable`, `::test_active_version_content_is_also_immutable`, `::test_fork_new_draft_version_copies_content_into_a_new_version` (5.A/5.B) |
| Invalid graph cannot be submitted for approval | Yes | `::test_submit_for_approval_rejects_unreachable_node_without_changing_status` (5.B), `tests/integration/test_algoritm_api.py::test_submit_for_approval_rejects_invalid_graph` (5.D, over real HTTP) |
| Uncovered branch blocks approval | Yes | `::test_submit_for_approval_rejects_uncovered_rule_branch` / `::test_submit_for_approval_accepts_covered_rule_branch` (5.B) |
| Financial policy activation requires two identities | Yes | `::test_activate_version_rejects_same_maker_and_checker_for_financial_node` / `accepts_different_maker_and_checker` (5.B), `test_algoritm_api.py::test_financial_impact_node_activation_requires_two_distinct_identities` (5.D) |
| Rollback restores behavior, log visible | **Partial** — `::test_activate_version_rollback_reactivates_a_suspended_version` (5.B) only asserted the status flip, never *behavior* (no simulation engine existed yet at 5.B) | **New in this task** |
| Kill switch stops new evaluations, journal/audit intact | **Partial** — `::test_kill_switch_suspends_active_version_and_logs_reason` (5.B) asserted the new transition's reason, never that *prior* journal entries survive unmodified, and never chained a subsequent reactivation | **New in this task** |
| Accessibility: keyboard alternative passes critical flows (WCAG 2.2 AA) | **Partial** — 5.D's `PolicyOutline.test.tsx` proved Tab-reachability (no keyboard trap) but ran no automated WCAG scanner | **New in this task** |

**Scope built this session:**
1. Two new integration tests in `tests/integration/test_policy_store.py`:
   `test_rollback_rehearsal_restores_active_versions_behavior_and_keeps_transition_log_visible` (uses 5.C's
   `simulation_engine.run_case` to prove the graph's *behavior* — not just its status — reverts on rollback,
   looked up dynamically via `list_versions_by_graph` rather than a hardcoded version id) and
   `test_kill_switch_rehearsal_preserves_prior_journal_and_allows_reactivation` (asserts every pre-kill-switch
   transition row survives byte-for-byte, and that the version can be reactivated afterward).
2. `apps/web/src/accessibility.test.tsx` — an `axe-core` (via `vitest-axe`) scan of every screen 5.D built:
   `App`'s connection form, `PolicyOutline` (with validation issues shown), `SimulationPanel` (with a run's
   results and an expanded execution trace), `TransitionHistory`. This is real, structural WCAG evidence,
   not a placeholder — it found and this task fixed one genuine violation (`SimulationPanel`'s per-case
   results table had an empty `<th>` for its actions column — `empty-table-header`, no text visible to
   screen readers).
3. This plan doc + an exit-gate evidence summary (`docs/reports/WORKLOG.md`, mirroring the Phase 4 exit-gate
   summary's table format) mapping every `PLAN-MISSION-5.md` §5 row to its concrete test evidence.

**Explicitly out of scope / recorded as an honest reading, not built:**
- **"Kill switch stops new evaluations"** is interpreted, same as 5.B's own reading, as *stopping future
  production routing to this version* — not as gating `POST /policy-versions/{id}/simulate`. Simulation/
  backtest is deliberately available regardless of a version's lifecycle status (an analyst investigating
  *why* a version was killed needs to be able to simulate it) — recorded explicitly here because it is a
  real interpretive choice about `FR-ALG-13`'s scope boundary, not an oversight. There is still no
  production evaluation/routing engine anywhere in this codebase (the same honest gap 5.B/5.C already
  recorded) — so the literal "in-flight evaluations complete in a defined way" half of `FR-ALG-13` remains
  unbuilt, unchanged from 5.B.
- No new HTTP routes, no new frontend screens — this task only adds test coverage and one one-line UI fix
  the coverage itself found.
- `FR-ALG-06` (sensitivity analysis) remains the same recorded gap from 5.C.

**Requirement IDs in play:** `FR-ALG-11`, `FR-ALG-03`, `FR-ALG-04`, `FR-ALG-12`/`FR-AUT-02`, `FR-ALG-13`,
`FR-ALG-14`, `FR-UX-02` (`PLAN-MISSION-5.md` §5's own exit-gate criteria).

---

## Task 1: rollback + kill-switch rehearsal tests

**Files:** update `tests/integration/test_policy_store.py`.

**Steps:**
- [ ] `test_rollback_rehearsal_restores_active_versions_behavior_and_keeps_transition_log_visible`: two
      versions of the same graph with distinguishably different single-node behavior (`reason_codes`);
      activate v2 (auto-suspends v1); run `packages.algorithm.simulation_engine.run_case` against v2 to
      confirm the difference is real; roll back (`activate_version` against the now-suspended v1); look up
      "whichever version `list_versions_by_graph` now reports active" (not a hardcoded id) and `run_case`
      against it, asserting v1's original `reason_codes` return; assert the full transition list for v1
      shows all seven entries across the whole rehearsal in order.
- [ ] `test_kill_switch_rehearsal_preserves_prior_journal_and_allows_reactivation`: full lifecycle to
      `active` (5 transitions); capture the transition list; `kill_switch`; assert every prior transition
      row is byte-for-byte unchanged (compared by id) and exactly one new row was appended; assert status is
      `suspended`; `activate_version` again (reactivation); assert status `active` and the transition count
      grew by one more.

## Task 2: automated accessibility scan

**Files:** `apps/web/src/accessibility.test.tsx`; `apps/web/package.json`/`package-lock.json` (add
`vitest-axe`, `axe-core` devDependencies); `apps/web/src/vitest.setup.ts` (register the matcher).

**Steps:**
- [ ] Add `vitest-axe`/`axe-core`; register `vitest-axe/matchers` via `expect.extend()` in
      `vitest.setup.ts` (the package's own `extend-expect` import only adds TypeScript types, not the
      runtime matcher — easy to miss, recorded as a real gotcha, not silently worked around).
- [ ] One `axe()` scan per screen 5.D built, each after the async content that screen actually shows is
      settled (validation issues rendered, a simulation run's results and an expanded trace visible,
      transitions loaded) — scanning only the empty/loading state would miss real violations in the content
      that actually appears.
- [ ] Fix whatever `axe` finds for real, rather than suppressing the rule — in this run, one violation
      (`SimulationPanel`'s empty actions-column `<th>`).
- [ ] `vitest-axe`'s ambient `.d.ts` doesn't resolve against this project's vitest 3.x types (a real gap in
      that package, confirmed: the matcher works at runtime, only `tsc --noEmit` complains) — isolate the
      one necessary type-cast in a single named helper (`expectNoViolations`) rather than scattering
      `as unknown` through every test.

## Task 3: close-out

**Steps:**
- [ ] Full gate (`pytest -m "not live_network"`, `ruff format --check`, `ruff check`, `mypy packages apps`,
      `check_v1_untouched.py`) green.
- [ ] Frontend `npm test` + `npm run build` green.
- [ ] `docs/reports/WORKLOG.md` exit-gate evidence summary (table mapping `PLAN-MISSION-5.md` §5's five
      criteria to concrete test file/name evidence, same format as the 2026-08-12 Phase 4 exit-gate entry)
      + `docs/decisions/OPEN-QUESTIONS.md` entry recording the kill-switch-does-not-gate-simulation reading.
