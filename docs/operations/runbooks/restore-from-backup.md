# Runbook: restore from backup

**Trigger:** production data loss or corruption serious enough that the
fastest safe recovery is restoring from the last known-good backup, rather
than a forward fix.

**This is the disaster-recovery case — not the pre-release drill.** For
"confirm the restore mechanism still works before a release", see
`docs/operations/runbook.md` step 3 and `scripts/run_restore_drill.py`
(Phase 6, task 6.C) instead; this document is for an actual incident
against the real target database.

## Response

1. **Stop writes to the affected database immediately** — every additional write after the corrupting event narrows what a restore can recover, and some writes may themselves need to be replayed or discarded depending on what happened.
2. Identify the backup to restore: `scripts/collect_signals.py`'s `backup.latest_backup_at` and `restore_drill.latest_passing` tell you the newest backup's age and whether a drill has ever proven a restore from a recent backup actually works — prefer the most recent backup that has a passing drill on record, not merely the most recent file, if there's any doubt about a newer backup's integrity.
3. Run `python scripts/restore.py --backup-path <path> --database-url <target>` against the **real target** only after confirming step 1 and after getting the same distinct-approver sign-off `docs/operations/runbook.md`'s step 5 requires for a release — a restore is at least as consequential as a deploy and should not be a unilateral action.
4. After restore, run `python scripts/check_invariants.py` and `python scripts/smoke_test.py` (per `docs/operations/runbook.md` steps 4/7) against the restored database before declaring it live again.
5. Record what happened: what was lost (the gap between the backup's timestamp and the incident), why, and the restore's outcome — in `docs/reports/WORKLOG.md`, same append-only convention as every other operational event in this project.

## Do not

- Do not restore directly over a database still receiving writes without stopping them first — `pg_restore` against a live, write-receiving target can itself corrupt state further.
- Do not skip the invariant/smoke checks "to save time" — a restore that silently reintroduces a structural problem is worse than the outage it was meant to fix.
