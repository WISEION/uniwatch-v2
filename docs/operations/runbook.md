# Operational runbook — running a release

**Status:** New (Phase 6 task 6.B, task 6 of 6.B). This is Gate 3/4/5 wiring
(master plan §22) turned into an ordered, followable sequence for an actual
release — it does not reinvent Gate 3/4/5's individual mechanisms, it
sequences them.
**Requirements:** master plan §22 Gate 3 ("operational runbook" line) and
Gate 3's "release notes and known limitations" line (the companion template,
`docs/operations/release-notes-template.md`), `NFR-REL-01..03`, `NFR-SEC-09`,
`INV-14`, `AGENTS.md` hard ban #6 (green CI is not production deployment
authorization).
**Scope:** the mechanical sequence a release operator follows to run one
release, per `docs/reports/PLAN-MISSION-6.md` §3 task 6.B and the Phase 6
pilot topology (`D-HOST`: local network only). It is not the cutover/rollback
decision itself — that is `docs/operations/cutover-plan.md`, referenced at
step 8, not restated here.

**Concurrent build note:** this runbook is being written alongside the
scripts and CI job it sequences. Where one of those isn't finished yet at the
time this doc is read, treat that step as "to be run" using the name/purpose
below — the sequence and its reasoning do not change once the script lands.

## Roles

Per master plan §25's governance/RACI table (already established, not
re-derived here): a **release operator** executes this sequence; a
**distinct approver** (a different identity from whoever initiated the
release) performs step 5's authorization; a **post-deploy verifier**
confirms step 7. The distinct-approver requirement is structural (`INV-14`,
`docs/adr/0005-authority-model.md`'s `FR-AUT-06`) — the same person cannot
run steps 2 and 5 for the same release.

## Sequence

### 1. Back up the target database

Run `scripts/backup.py` against the target DB before anything else touches
it. A release that fails partway through should never leave the operator
without a pre-release backup to fall back on. Record the backup's location/
identifier — step 5 and step 8 (if needed) both refer back to it.

### 2. Confirm CI is green for the exact commit being released

Check that the Fast gate, Full gate, `build-images`, and `security-scan`
jobs (`.github/workflows/ci.yml`) all report success for the specific commit
SHA being released — not merely "the branch's most recent green run," since
a later push can move the branch head without the release actually being
re-tested. This document does not restate what each job checks; see
`.github/workflows/ci.yml` and `.ci/README.md` for that.

Per `AGENTS.md` hard ban #6 and `INV-14`: green CI at this step is a
precondition for the rest of this sequence, not the deployment authorization
itself — that only happens at step 5.

### 3. Check whether the restore drill is still current

Before deploying, confirm a restore drill has actually been performed and
logged — not merely scheduled — and that its result is a pass. The real
mechanism (Phase 6 task 6.C) is `scripts/run_restore_drill.py`: it runs
`scripts/backup.py` against `--source-database-url`, restores that backup
into `--drill-database-url` (a disposable scratch database, never the
source or a production target), and records the pass/fail result into the
SOURCE database's `restore_drill_runs` table via
`packages/platform/restore_drill.py::record_restore_drill`. Invoke it as a
module, not as a bare script:

```
python -m scripts.run_restore_drill --source-database-url <source> --drill-database-url <scratch> --backup-dir <dir>
```

`python scripts/run_restore_drill.py ...` fails with
`ModuleNotFoundError` — the script does an absolute `from scripts.backup
import ...` import, which only resolves when `scripts` is imported as a
package (`python -m scripts.run_restore_drill`), not when the script is
run directly. This is a real, confirmed limitation of the script, not a
typo to avoid.

Check "has a drill been logged, and did it pass" via
`packages/platform/restore_drill.py::latest_passing_drill`, or more simply
by reading `scripts/collect_signals.py`'s `restore_drill.latest_passing`
field in its JSON payload — a `null` value there means no passing drill has
ever been recorded for this environment.

**What "recent enough" means is not yet defined.** `D-SLO` (`TBD-01`,
`TBD-02`) is the open decision that would give a restore-drill an explicit
freshness window (e.g. "no older than N days"); until it resolves, there is
no numeric staleness threshold to check against, and this document does not
invent one (`AGENTS.md` hard ban #2). Until `D-SLO` resolves, "is the drill
current" is a qualitative judgment by the release operator and approver —
based on whether anything about the backup/restore mechanism, schema, or
target environment has materially changed since the last drill — not a
computed pass/fail. If there is any doubt, re-run the drill before
proceeding rather than deploying against a drill whose currency is in
question.

If no restore drill has ever been logged for this environment (i.e.
`restore_drill.latest_passing` is `null`), this step fails outright —
proceed to step 8's rollback/blocked-release handling instead of continuing
to step 4.

### 4. Run the live invariant check

Run `scripts/check_invariants.py` against the target DB. This is a real,
live-DB check of the invariants this project treats as structural (e.g. the
four-layer data model's layer ordering, RBAC deny-by-default, synthetic/real
isolation) — distinct from the unit/integration test suite, which runs
against ephemeral test databases, not the actual release target. A failure
here stops the sequence — see step 8.

### 5. Run deployment authorization

Run `scripts/authorize_deployment.py <PR number>` for the PR being released.

This is the mechanical half of Gate 4 (`master plan §22`, `INV-14`,
`docs/adr/0005-authority-model.md`'s `FR-AUT-06`). It:

- Verifies the approver identity invoking it is distinct from the PR's
  initiator.
- Checks the commit under release against `docs/operations/release-manifest.md`'s
  manifest shape — confirming the digest about to be deployed matches the
  digest CI actually built and tested for this commit (guards against the
  v1 RN-11/RN-12 class of a tag or version drifting from what was reviewed).
- Checks DB schema compatibility for the target environment.
- Records the authorization (the `deployment_authorizations` record
  referenced in `docs/operations/release-notes-template.md`).

**What this step does not check:** it is not a substitute for human review
of the code itself — that review already happened as part of the normal PR
process before CI went green in step 2. This script checks *authorization
mechanics* (distinct identity, digest match, schema compatibility), not code
correctness or design quality.

A failure here (same-identity approver, digest mismatch, incompatible
schema) blocks the release — do not proceed to step 6 by manually working
around the check.

### 6. Deploy

`docker compose -f docker-compose.local.yml up`, per task 6.A's topology
(`D-HOST`: local network only). This document does not restate the compose
file's contents or `docs/operations/container-conventions.md`'s image rules
— it only sequences the deploy here, after authorization, never before.

### 7. Run the smoke test

Run `scripts/smoke_test.py` against the now-live deployment. This exercises
real endpoints by role (per the pilot's RBAC model) against the actual
running services — not the test suite's mocked/ephemeral environment — to
confirm the deployment is actually serving traffic correctly before the
release is considered complete. The post-deploy verifier confirms this
step's result, per Gate 5 (`master plan §22`, `AGENTS.md` hard ban #6: green
CI, and now a successful deploy, still is not itself "done" until this
verification happens).

### 8. If step 3, 4, or 7 fails

Do not attempt to invent a rollback procedure here. Follow
`docs/operations/cutover-plan.md` §3's rollback plan — stop routing to v2
and continue on v1 (v1 was never stopped or written to during the pilot, so
there is no v2-side data to unwind), with the same distinct-approver
discipline as the forward deployment, and the same append-only audit
record of actor/reason/evidence. This runbook does not re-derive that
mechanism.

## What this runbook deliberately does not cover

- Numeric SLOs, freshness windows, or rollback trigger thresholds — `D-SLO`
  (`TBD-01`, `TBD-02`) remains open; see `docs/operations/cutover-plan.md` §4
  and `docs/decisions/OPEN-QUESTIONS.md` for the current status of that
  decision.
- Pilot user/permission-matrix specifics (`D-PILOT`) — not this document's
  concern; step 7's role-based smoke test uses whatever roles exist at the
  time it runs.
- The observability signals/alerts that would surface a problem *between*
  releases (Phase 6 task 6.C) — this runbook is release-time only.
