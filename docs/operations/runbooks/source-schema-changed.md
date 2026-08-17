# Runbook: source schema changed

**Trigger:** `scripts/check_alerts.py`'s `exception_queue_has_open_items`
fires (or a manual `scripts/check_invariants.py`-adjacent look at
`exception_queue` shows a fresh row), and its `exception_type` is
`schema_drift`.

## What happened

One of `packages/tender`'s connectors (`etender_connector.py`,
`worldbank_connector.py`) called `packages/tender/schema_drift.py`'s
detection and it found the live source's response no longer matches that
connector's frozen `SourceContract`. Per `packages/tender`'s own
architecture (see `CLAUDE.md`), the job caught `SchemaDriftDetected` and
called `enqueue_exception(exception_type="schema_drift", category="needs_human", ...)`
instead of silently mapping the new shape — the response was **not**
ingested.

## Response

1. Query the open exception: `SELECT * FROM exception_queue WHERE exception_type = 'schema_drift' AND status = 'open' ORDER BY first_seen_at DESC;` — `reason`, `raw_ref`, and `correlation_id` identify exactly which contract failed and why.
2. Follow `raw_ref` to the `raw_snapshots` row (`packages/tender/raw_snapshot.py::get_raw_snapshot`) to see the actual raw response that triggered the drift.
3. Compare against the relevant `SourceContract` (`etender_contract.py`/`worldbank_contract.py`) to determine whether the source genuinely changed shape or a one-off malformed response occurred.
4. If the source genuinely changed: update the contract, add/adjust the connector's mapping, and add a regression test using the captured raw snapshot as a fixture — never edit the contract without a fixture that would have caught the drift.
5. Once fixed and merged/deployed, close the exception: `packages/platform/exception_queue.py::close_exception(conn, id=..., reason="contract updated in <PR>", closed_by="<your identity>")`.
6. If the ingestion job needs re-running for the affected range now that the contract is fixed, re-enqueue via the job's own `enqueue_*` entry point (per `packages/platform/jobs.py`'s job-identity model, a new range/params always gets a new job row, never a reused checkpoint).

## Do not

- Do not manually edit `exception_queue.status` to `'closed'` without following step 4/5 — that erases the actionable trail this table exists to preserve.
- Do not "fix" drift by loosening the contract to accept anything — a `SourceContract` exists specifically so an unexpected shape is caught, not silently absorbed (`AGENTS.md` hard ban #3).
