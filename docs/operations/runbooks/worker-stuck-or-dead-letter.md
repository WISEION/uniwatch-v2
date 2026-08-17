# Runbook: worker stuck or dead-lettered job

**Trigger:** `scripts/check_alerts.py`'s `dead_lettered_jobs_present`
fires, or `scripts/collect_signals.py`'s `job_queue.by_status` shows a
growing `leased` count with no matching `completed`/`failed` movement
(a worker likely died mid-lease without its lease expiring cleanly yet).

## What happened

`packages/platform/jobs.py`'s `fail_retry` moves a job to `'failed'`
(dead-lettered) only once `attempt >= max_attempts` — every retry before
that goes back to `'pending'` with an exponential backoff
(`compute_backoff_seconds`). A `'failed'` job has exhausted its retry
budget and needs a human, not another automatic attempt. A `'leased'` job
whose worker died keeps its row locked until `lease_expires_at` passes,
at which point `claim`'s own query already treats it as reclaimable
(`status = 'leased' AND lease_expires_at < now()`) — so a *stuck* worker
(long-running, not dead) looks identical to a live one until the lease
window elapses.

## Response

1. Dead-lettered: `SELECT * FROM jobs WHERE status = 'failed' ORDER BY updated_at DESC;` (or `packages/platform/jobs.py::JobStore.list_dead_lettered`). `last_error` holds the final failure reason; `checkpoint` holds however far it got.
2. Diagnose from `last_error` and `job_type`/`params`/`source`/`range_start`/`range_end` — the job's full identity is immutable from `enqueue` time (`FR-JOB-02`), so the exact input that failed is always reconstructible.
3. Once the underlying cause is fixed, do not resurrect the same row — per `FR-JOB-02`/`FR-JOB-06`, a job's identity is fixed at enqueue and never mutated. Enqueue a **new** job with the same `job_type`/`source`/range via that job type's own `enqueue_*` entry point.
4. Stuck-but-not-dead (`leased`, lease not yet expired, but no checkpoint progress for an unreasonable time): check the worker process (`apps/worker/main.py`) is actually alive and processing — if it's hung, kill the worker process; `claim`'s reclaim logic picks the job back up automatically once `lease_expires_at` passes, no manual row edit needed.

## Do not

- Do not manually `UPDATE jobs SET status = 'pending' WHERE id = ...` to force a retry — this bypasses the `attempt` counter and backoff bookkeeping `fail_retry` maintains, and can reintroduce a job past its intended `max_attempts`.
- Do not delete a dead-lettered row — it's the only record of what was attempted and why it failed.
