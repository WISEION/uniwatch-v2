# Cutover / rollback plan (Phase 6 pilot)

**Status:** Document, not code — this is the artifact `docs/reports/PLAN-MISSION-6.md` §3 task 6.A's
fourth row calls for ("Cutover criteria и rollback plan утверждаются заранее (документ, не код)"),
approved before the pilot starts rather than decided in the middle of it. It records criteria and
process; it does not itself implement any of the mechanisms it references.
**Requirements:** `FR-MIG-03`, master plan §24 (Миграция и coexistence с v1), §25 (Governance и RACI),
§22 Gates 3-5, `INV-14`, `NFR-REL-01..03`, `NFR-OPS-01/02`.
**Scope:** the controlled pilot described in `docs/reports/PLAN-MISSION-6.md` (Phase 6) only. This is
not a general production-release runbook — Gate 3/4/5 wiring (task 6.B) and the observability signals
this plan's evidence depends on (task 6.C) are separate, not-yet-built tasks this document references
rather than duplicates.

## 1. Ground rule: v1 is untouched throughout

Per master plan §24.1, v1 and v2 run in parallel until a formal cutover — this is not a decision this
document makes, it is a structural property already enforced elsewhere in this codebase:

- v2 has no write path into v1 by construction (`NEG-01`/`NEG-02`); `tools/check_v1_untouched.py` checks
  this after every change.
- The shadow-comparison harness that produces this plan's first cutover criterion (below) is explicitly
  read-only against v1 (master plan §24.4: "v2 не пишет обратно").

Because of this, "rollback" in this plan never means undoing a v2-side migration or reconciling data v2
took ownership of — v2 never becomes the system of record during the pilot. See §3.

## 2. Cutover criteria

Cutover — routing pilot users'/traffic's production use to v2 instead of v1 — requires **all** of the
following to hold, for the agreed pilot date/source range (the range itself is set when the pilot
starts, not by this document):

1. **Shadow comparison shows no unresolved `v2_defect` or `v1_loss` classification.** The
   shadow-comparison harness (`FR-MIG-03`, master plan §24.4 — file layout not fixed yet at the time of
   writing, tracked as part of task 6.A/6.E) classifies every mismatch between v1 and v2 over the pilot's
   bounded source/date range into one of four buckets: `v1_loss`, `v2_defect`, `source_drift`, or
   `expected_semantic_difference`. Cutover requires zero mismatches left in the first two buckets —
   `source_drift` and `expected_semantic_difference` are allowed to remain, since they are not v2
   correctness issues. The shadow-comparison report itself (task 6.E: "Shadow comparison отчёт: все
   расхождения классифицированы, критических нерешённых потерь данных нет") is the evidence artifact;
   this plan does not restate its methodology.
2. **Restore drill passes.** A real backup restore (task 6.B: "Backup + проверенный restore", `NFR-REL-01`)
   has been performed and its result logged, not merely scheduled. Not yet built as of this document — a
   dependency of this plan, not something this plan can certify in advance.
3. **User acceptance testing passes.** Task 6.E's UAT with the actual pilot users (per `D-PILOT`, once
   resolved — see §4) reports no blocking findings. Not yet built as of this document.

These three map directly to three of Phase 6's five exit-gate criteria (`docs/reports/PLAN-MISSION-6.md`
§4): "нет критических нерешённых потерь данных" (criterion 1 above), "restore drill проходит" (criterion
2), "user acceptance пройден" (criterion 3). The exit gate's other two criteria — freshness/completeness
against an agreed target, and production deployment approved by a distinct identity — are Gate
3/4/5-level concerns (task 6.B) that this document does not re-derive; cutover cannot happen before
Gate 4 authorization in any case (§3).

**What this document deliberately does not put a number on:** freshness/completeness targets,
availability, RPO/RTO, and any other operational SLA figure remain `D-SLO` (`TBD-01`: SLO/latency/
freshness; `TBD-02`: RPO/RTO), per `docs/reports/PLAN-MISSION-6.md` §5 and `docs/CONTEXT.md`'s open-questions
table — open, not defaulted (`AGENTS.md` §2 hard ban #2). Task 6.C's SLO *categories* (interactive p95
latency, source freshness window, job start/completion lag, BOQ completeness target, availability,
notification delay, RPO/RTO, incident acknowledgment) are fixed without numbers; this plan's cutover
criteria list only covers what is measurable by mechanisms that either already exist (shadow comparison)
or are already scoped as concrete pass/fail tasks (restore drill, UAT) — it does not invent a fourth,
numeric criterion to fill the D-SLO gap. When `D-SLO` resolves, the exit gate's freshness/completeness
criterion becomes checkable against a real target; until then it is tracked as open, not silently treated
as satisfied.

## 3. Rollback plan

**What rollback means here:** stop routing pilot users/traffic to v2 and continue on v1 — not a
data-migration undo. Because v2 never became the system of record (§1), there is no v2-side data or
state to unwind; a rollback is a routing decision, not a technical recovery operation.

**Who decides and who executes:** per master plan §25's Governance/RACI table, the "Production
deployment" row is `Responsible: Release operator`, `Approver: a different approver` (distinct identity
from whoever initiated the deployment/cutover — `INV-14`, `AGENTS.md` hard ban #6: green CI is not
production deployment authorization), `Independent check: Post-deploy verifier`. A rollback decision
during the pilot follows the same accountability split as the original cutover: the release operator
executes it, but the decision to invoke rollback is not the release operator's alone to make — it
follows the same distinct-approver discipline as the forward deployment did, since a rollback is itself
a production-deployment-affecting action.

**Rollback triggers not yet numerically defined:** what threshold of, say, freshness degradation or error
rate during the pilot should *itself* trigger a rollback decision is not decided by this document and is
not invented here — it depends on the same `D-SLO`/`TBD-01`/`TBD-02` figures as §2's open item, plus
task 6.C's alerting thresholds once built. Until those resolve, a rollback decision during the pilot is
made on qualitative evidence (an unresolved `v2_defect` discovered mid-pilot, a failed invariant, a
security incident) reviewed by the same distinct-approver pair, not against a pre-agreed numeric trigger.
This gap is recorded here rather than papered over with an invented number.

**Mechanically, a rollback is:**
1. Stop directing pilot user sessions/traffic to v2 (task 6.A's identity/routing layer — not yet built
   at the time of writing).
2. v1 requires no action — it was never stopped, migrated, or written to during the pilot (§1).
3. The rollback event itself is logged with actor, reason, and evidence, per the same append-only audit
   discipline `packages/platform/audit.py` already applies to admin actions elsewhere in this codebase —
   a rollback is an operational decision of the same weight as the deployment it reverses, and gets the
   same record-keeping, not a quieter one.

## 4. Open decisions referenced, not resolved, by this plan

| ID | What it blocks here | Status |
|---|---|---|
| `D-SLO` (`TBD-01`, `TBD-02`) | Numeric freshness/completeness/availability/RPO/RTO targets for §2's freshness criterion and any quantitative rollback trigger | Open — `docs/reports/PLAN-MISSION-6.md` §5, `docs/CONTEXT.md` |
| `D-PILOT` | Exactly which users/permission matrix are "pilot users" for §3's routing decision | Open — blocks task 6.D, not this document |

No number or identity for either has been substituted here. This plan is written so that resolving
`D-SLO` fills in a concrete freshness/rollback-trigger check without needing this document rewritten,
and resolving `D-PILOT` defines who "stop routing" in §3 actually applies to without changing the
rollback mechanics themselves.
