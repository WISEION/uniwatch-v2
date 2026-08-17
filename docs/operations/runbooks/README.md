# Incident runbooks (master plan §23.4)

Nine incident-response runbooks, one per master-plan §23.4 category. These
are distinct from `docs/operations/runbook.md` (the linear pre-release
sequence for *running a release*) and `docs/operations/cutover-plan.md`
(the v1→v2 cutover/rollback decision) — each doc here is "this specific bad
thing just happened in a live environment, what do you do right now."

| Category (§23.4) | Runbook |
|---|---|
| Source schema changed | [source-schema-changed.md](source-schema-changed.md) |
| BOQ reconciliation failed | [boq-reconciliation-failed.md](boq-reconciliation-failed.md) |
| Worker stuck/dead letter | [worker-stuck-or-dead-letter.md](worker-stuck-or-dead-letter.md) |
| Database invariant failed | [database-invariant-failed.md](database-invariant-failed.md) |
| Restore from backup | [restore-from-backup.md](restore-from-backup.md) |
| Policy/model kill switch | [policy-model-kill-switch.md](policy-model-kill-switch.md) |
| Rollback release | [rollback-release.md](rollback-release.md) |
| Suspected credential/PII incident | [suspected-credential-or-pii-incident.md](suspected-credential-or-pii-incident.md) |
| Vendor tenant isolation incident | [vendor-tenant-isolation-incident.md](vendor-tenant-isolation-incident.md) |
