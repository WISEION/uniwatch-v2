# Runbook: rollback release

**Trigger:** a just-deployed release is broken badly enough that the
fastest safe path is reverting to the prior release rather than
forward-fixing.

## Response

This runbook is a pointer, not a re-derivation: `docs/operations/runbook.md`
step 8 ("If step 3, 4, or 7 fails") already defines what happens when a
release's own post-deploy checks fail, and `docs/operations/cutover-plan.md`
defines rollback mechanics for the v1→v2 pilot specifically ("stop routing
to v2" — v2 never becomes the system of record during the pilot, so
rollback is a routing change, not a data-undo). Follow those two documents
directly:

1. `docs/operations/runbook.md` step 8 for the immediate "this release failed its own gate" sequence.
2. `docs/operations/cutover-plan.md` for what "stop routing to v2" means concretely in this pilot's topology (`D-HOST`: local network only).
3. If the release's problem involves data written since deploy that must not be lost, treat this as a `restore-from-backup.md` situation instead (or in addition) — a routing rollback alone does not undo bad writes already made against the new release's schema/logic.
4. Record the rollback and its cause in `docs/reports/WORKLOG.md`, same as every other operational event.

## Do not

- Do not re-derive a separate rollback mechanism here — this project already has two authoritative sources for it; a third, slightly different version would only create drift.
