# SLO categories (Phase 6, task 6.C)

**Status:** Categories only — no numbers. `D-SLO` (`TBD-01`, `TBD-02`) is
open (`docs/decisions/OPEN-QUESTIONS.md`); master plan §23.3 is explicit
that numbers are approved only after a real load baseline, and
`AGENTS.md` hard ban #2 forbids substituting a "reasonable" default in the
meantime. This document exists so the categories master plan §23.3 names
have one canonical place to live before their numbers are decided — not to
pre-commit to a number by omission.

| Category | What it would bound | Where it's measured today (§23.1 signal) |
|---|---|---|
| Interactive p95 latency | Time to first byte for an interactive API route | Not instrumented yet — no request-latency middleware exists in `apps/api_tender`/`apps/api_vendor` (see `docs/decisions/OPEN-QUESTIONS.md`'s 2026-08-17 entry) |
| Source freshness window | How old the last successful fetch from a source may be before it's "stale" | `scripts/collect_signals.py`'s `source_freshness.last_fetched_at_by_source`; `packages/tender/freshness_alerts.py::source_never_succeeded` only catches the zero-fetches case, not a staleness window |
| Job start/completion lag | Time from job enqueue to claim, and claim to completion | `scripts/collect_signals.py`'s `job_queue.by_status`; per-job timestamps are on the `jobs` row (`created_at`/`updated_at`) but no aggregate lag query exists yet |
| BOQ completeness target | What fraction of a tender's BOQ money must reconcile before treating it as usable | `scripts/collect_signals.py`'s `boq_completeness.by_status` |
| Availability | Fraction of time `/health/ready` reports `ok` | `packages/platform/app_factory.py`'s readiness probe; no uptime aggregation exists yet |
| Notification delay | Time from a triggering event to notification delivery | Not applicable today — no notifications mechanism exists in this repo (see `scripts/collect_signals.py`'s `notification_delivery` entry) |
| RPO/RTO | Maximum acceptable data loss / time to restore after an incident | `scripts/collect_signals.py`'s `restore_drill.latest_passing`/`backup.latest_backup_at` measure the *evidence* (when was this last proven); the *target* window is `D-SLO` |
| Incident acknowledgment | Time from an alert firing to a human acknowledging it | `scripts/check_alerts.py` produces the firing signal; no acknowledgment-tracking exists (would require a paging/on-call tool this pilot does not have, per `D-HOST`) |

**Do not add a number to this table** until `D-SLO` resolves — extend the
table with new categories as new signals are built, but leave the "target"
column absent rather than estimated.
