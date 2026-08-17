# Runbook: BOQ reconciliation failed

**Trigger:** `scripts/collect_signals.py`'s `boq_completeness.by_status`
shows a `boq_import` row stuck at `incomplete` or
`source_exhausted_unverified` for longer than expected, or
`packages/tender/boq_completeness.py::mark_import_stalled` was called for
a specific `(source, event_id)`.

## What happened

Per `INV-04` (`AGENTS.md` hard ban #5), a BOQ is `complete` only after
proven page/row reconciliation. `source_exhausted_unverified` means the
source ran out of pages to serve but never gave a total that would let
`boq_completeness.py` prove every page was actually fetched —
`incomplete` means fetching stopped (error, timeout, stall) before the
source was exhausted.

## Response

1. `SELECT * FROM boq_import WHERE status IN ('incomplete', 'source_exhausted_unverified') ORDER BY updated_at DESC;` to find the affected `(source, event_id)` rows. `missing_pages` and `page_checksums` show exactly what is/isn't accounted for.
2. For `incomplete`: check `exception_queue`/job logs for the underlying `bom_lines_job.py` run against that `(source, event_id)` — the stall/error reason lives there, not in `boq_import` itself.
3. Re-run the BOQ ingestion job for that specific `(source, event_id)` once the underlying cause (network, contract drift, rate limit) is resolved — `record_page_fetched` is idempotent per page, so a retry does not double-count already-fetched pages.
4. For `source_exhausted_unverified`: this is not automatically fixable — the source itself never provided a verifiable total. Confirm with a human reviewer whether the fetched lines are usable as-is (flagged, not silently treated as complete) before any downstream matching (`packages/decision/matching.py`) consumes this BOQ.

## Do not

- Do not manually set a `boq_import` row's `status` to `'complete'` to unblock downstream work — `INV-04` makes that a hard ban; `source_exhausted_unverified` is the honest terminal state when a source gives no way to prove completeness.
