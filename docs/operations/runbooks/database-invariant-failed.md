# Runbook: database invariant failed

**Trigger:** `scripts/check_invariants.py` (or `scripts/check_alerts.py`'s
`invariant_violation_detected`) reports a `FAIL` line.

## What happened

One of `packages/platform/invariant_checks.py`'s live-DB structural checks
(`no_orphaned_notifications`, `policy_versions_one_active_per_graph`,
`no_orphaned_user_roles`) found the actual, currently-running database in a
state this project treats as structurally impossible — not a test-suite
finding against an ephemeral DB, a real finding against the real target.

## Response

1. Run `python scripts/check_invariants.py` directly against the affected environment's `DATABASE_URL` to get every failing check's `detail` (which rows, how many — never just "false", per hard ban #3).
2. `no_orphaned_user_roles` failing: a `users.role_id` points at a `roles` row that no longer exists. RBAC's deny-by-default resolution (`packages/platform/rbac/`) already treats an unresolvable role as no-access, so this is not an active security hole, but indicates a data-integrity bug (a role was deleted without reassigning its users) that needs a real fix, not just a one-off cleanup query.
3. `policy_versions_one_active_per_graph` failing: more than one `policy_versions` row is `status = 'active'` for the same `policy_graph_id` — the partial unique index this invariant checks should make this impossible via normal application code (`packages/algorithm/policy_store.py::activate_version`). Treat this as a serious finding — check for direct DB access outside the application (a manual `UPDATE`, a migration that bypassed the store) before assuming it's a code bug.
4. Do not write an ad hoc fix query without first reproducing how the bad state was reached — the same bug will recur otherwise. If a genuine application-code bug is found, treat it with the same priority as any other correctness bug in this codebase (test-first fix, per `AGENTS.md`).

## Do not

- Do not silence the check by removing rows without understanding root cause — this is a structural-integrity signal, not noise.
- Do not skip Gate 5 (post-deploy invariant check) on a future release "because it failed once and we understand why" — each release re-proves the invariant against that release's actual resulting state.
