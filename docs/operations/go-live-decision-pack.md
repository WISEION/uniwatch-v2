# Go-live / rollback decision pack — template

**Status:** Template only. No pilot go-live decision has happened yet as of
this document — do not fill this in with real content until the pilot has
actually run long enough to produce the evidence each section asks for.
Copy this file to a dated decision-pack file per go-live review (e.g.
`docs/operations/releases/2026-MM-DD-go-live-decision.md`) and fill in each
section; do not edit this template in place with real data.

**Requirements:** `docs/reports/PLAN-MISSION-6.md` §3 task 6.D's third line
item ("go-live/rollback decision pack: summarizes shadow comparison
results, restore drill status, user acceptance, ready for a production
authorization verdict") and master plan §22 Gate 4 (production
authorization). This is the document a distinct approver reads before
deciding whether the pilot is ready to go live — it does not replace
`scripts/authorize_deployment.py`'s mechanical check (that verifies a
specific commit/digest/schema-version triple; this pack is about whether
the *pilot itself* is ready, a judgment call, not a mechanical one).

---

## Decision: `<pilot identifier / date range, e.g. "2026-08 pilot, weeks 1-4">`

### Shadow comparison results

`packages/tender/shadow_comparison.py`'s classification functions are pure
and currently unpersisted (`docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-17
task 6.C entry #2, assumption 2 — no run-history table exists yet). Until
that gap is closed, this section is filled in manually from whatever
comparison runs were actually performed and recorded (e.g. in
`docs/reports/WORKLOG.md`), not from an automated report:

- Comparison period covered:
- Total tenders compared:
- Discrepancies found, by classification:
- **Any unresolved critical data-loss discrepancy?** (must be "no" before
  go-live per master plan §18 Phase 6's exit-gate wording)

### Restore drill status

Pull directly from `packages/platform/restore_drill.py::latest_passing_drill`
(or `scripts/collect_signals.py`'s `restore_drill.latest_passing` field) —
do not hand-write a date without checking the actual table:

- Latest passing drill: `<backup_filename, target_database, drilled_at,
  from the actual latest_passing_drill row — "none recorded" if it returns
  null, never left blank or guessed>`
- Is the drill's currency still valid per `docs/operations/runbook.md`
  step 3's qualitative judgment (has anything about the backup/restore
  mechanism, schema, or target environment materially changed since)?

### User acceptance

No dedicated UAT sign-off mechanism exists in this codebase as of task 6.D
— `packages/platform/pilot_feedback.py`'s queue (see
`docs/operations/pilot-onboarding.md`) is the closest real signal available
today: an actively-used, low-friction feedback channel, not a formal
acceptance test. Until a real UAT process is designed, fill this section in
from what's actually observable:

- Number of pilot users who have signed in at least once (out of the 12
  provisioned by `scripts/seed_pilot_users.py`):
- Open feedback items (`GET /pilot-feedback?status=open`, requires
  `platform.feedback.triage`), by category:
- Resolved feedback items, and whether any resolution revealed a defect
  serious enough to block go-live:
- **Explicit judgment call:** is silence (a pilot user who hasn't submitted
  feedback) acceptance, or non-engagement? State which interpretation is
  being used here and why — do not silently assume "no news is good news."

### Production authorization verdict

- **Recommendation:** `<go / no-go / conditional>`, with the specific
  condition(s) if conditional.
- **Rationale:** tie the recommendation back to the three sections above —
  do not introduce new criteria here that weren't evidenced above.
- Once a verdict is reached, the actual authorization mechanics (distinct
  approver, commit↔digest check, schema check) go through
  `scripts/authorize_deployment.py` per `docs/operations/runbook.md` step 5
  — this pack is the judgment input to that step, not a replacement for it.

### If the verdict is no-go or rollback

Point to `docs/operations/runbooks/rollback-release.md` and
`docs/operations/cutover-plan.md` for the mechanics — this pack records
*why* the decision was made, not *how* to execute it.
