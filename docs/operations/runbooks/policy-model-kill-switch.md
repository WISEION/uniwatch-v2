# Runbook: policy/model kill switch

**Trigger:** an active policy graph version (`packages/algorithm`) is
producing wrong/harmful decisions and needs to stop being used immediately.

## What happened / what to do

This project's only kill switch today is `packages/algorithm/policy_store.py::kill_switch`
(Phase 5, task 5.B — proven by
`tests/integration/test_policy_store.py::test_kill_switch_rehearsal_preserves_prior_journal_and_allows_reactivation`).
It is policy-graph-specific: there is no general job/worker emergency-stop
mechanism in this codebase (recorded as an honest gap in task 6.B's
WORKLOG entry — not built here either).

1. Identify the affected `policy_graph_id`/active `policy_version_id` — `scripts/collect_signals.py`'s `policy_version_usage.active_versions` lists every currently-active version across every graph.
2. Call `kill_switch` (via `apps/api_tender/routers/algoritm.py`'s HTTP surface, or directly against `packages/algorithm/policy_store.py` for an operator with DB access) against that version.
3. Confirm the version's status is no longer `active` and that `policy_version_transitions` recorded the change — per the 5.E rehearsal test, all prior transition history remains intact, byte-for-byte, and the version can be reactivated later once the underlying issue is fixed.
4. "Kill switch stops new evaluations" is interpreted as stopping future production routing — `packages/algorithm/simulation_engine.py`'s simulate/backtest endpoints intentionally remain usable against a killed version, so an analyst can still investigate what happened (this interpretation is recorded in task 5.E's WORKLOG entry, not re-decided here).
5. There is no production evaluation/routing engine in this codebase yet (same gap 5.B/5.C/5.E already recorded) — if a killed policy version was somehow still being consulted by a real decision path outside `packages/algorithm`'s own tested surface, that is itself a bug to find and fix, not something this runbook's kill switch alone resolves.

## Do not

- Do not delete or edit `policy_version_transitions` rows to "clean up" a kill event — it is the append-only rehearsal evidence this exact runbook's category exists to rely on.
