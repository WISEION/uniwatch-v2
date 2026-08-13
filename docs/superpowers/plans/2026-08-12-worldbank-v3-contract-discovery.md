# World Bank Projects API `v3` contract discovery — Implementation Plan

> **Task 1 outcome (2026-08-12, same session as authored):** Resolved, cleanly — see the end of Task 1
> below. `v3` has a `status` field all along; it is simply opt-in via the `fl=` (field list) query
> parameter, which this plan's earlier ad hoc `curl` probes never passed. No proxy heuristic is needed.
> Task 2 (the actual connector migration) remains unscoped/not started, per this plan's own scope
> boundary — this outcome note only closes the reconnaissance question, not the migration.

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention (see `docs/reports/WORKLOG.md`). No subagent handoff. Steps use
> checkbox (`- [ ]`) syntax for tracking.

**Goal:** Resolve the open item recorded in `docs/decisions/OPEN-QUESTIONS.md` (2026-08-12, two entries:
"Finding: the World Bank JSON API this codebase's connector ingests from appears stale" and its
follow-up) — the `v2` endpoint `packages/tender/worldbank_connector.py` actually calls
(`search.worldbank.org/api/v2/projects`) is confirmed stale for Azerbaijan since roughly early/mid-2024,
while a `v3` endpoint on the same host returns current data. This plan is **reconnaissance only**, in
the same two-step discipline task 1.A used for eTender (capture the real contract first, build against
it second) — it does **not** commit to a migration approach, because the one thing already confirmed is
that `v3`'s record shape has no `status`/`projectstatusdisplay` field, and its "not yet approved" records
(`P515029`, `P508792`) still populate `boardapprovaldate`/`borrower`/`impagency` — so `v2`'s existing
proxy (treat those three fields' total absence as the Pipeline marker, per
`fixtures/tender-snapshots/worldbank/MANIFEST.md`) does not carry over unmodified. Inventing a
replacement proxy without confirming it against enough real, live-labeled examples would fabricate a
data contract this codebase has no source for (hard ban #2's spirit, applied to a discovered contract
rather than a financial number).

**Scope boundary:** This plan does not touch `packages/tender/worldbank_connector.py`,
`worldbank_contract.py`, `worldbank_pipeline_job.py`, or `signal_model.py`. It produces evidence and a
recorded conclusion; a follow-on task (out of this plan's scope) migrates the connector once the
conclusion is in hand. This also does not block Phase 5 kickoff — it is a data-quality fix on an
already-shipped Phase 2 connector, orthogonal to the phase sequencing `AGENTS.md` §4 governs.

## Global Constraints

- **No guessed status proxy.** Task 1 below must check candidate signals (see options list) against
  enough real, independently-labeled examples (status already known from the live HTML site or `v2`)
  before this plan can name one as reliable. If no candidate fully separates `Pipeline` from
  `Active`/`Closed`/`Dropped` across the sample, that is recorded as the honest outcome — not papered
  over with a partial heuristic presented as settled.
- **New fixtures are real, live captures, never hand-typed.** Any new file under
  `fixtures/tender-snapshots/worldbank/` follows the existing `MANIFEST.md` convention: exact response
  bytes, HTTP status, URL, sha256, capture date.
- Requirement IDs in play: `P309` (this connector's original acceptance criterion, already met on `v2`
  at the time it was built — this plan does not reopen whether `v2` satisfied `P309` in 2026-08-05, only
  whether it still reflects reality now), `INV-15`/`INV-16` (source_ref/raw-addressability — any new
  fixture must satisfy these the same way the existing ones do).

---

## Task 1: Determine `v3`'s real status signal, or confirm none exists at the list-endpoint level

**Files:**
- Create: `fixtures/tender-snapshots/worldbank/az_v3_all_page_os0.raw.json` (real capture of
  `https://search.worldbank.org/api/v3/projects?format=json&countrycode_exact=AZ&rows=100&os=0`, all 95
  current AZ records in one page — confirmed in this session's ad hoc verification that `rows=100`
  returns the full 95 without needing pagination).
- Update: `fixtures/tender-snapshots/worldbank/MANIFEST.md` (new entry, same table format).
- No code changes.

**Steps:**
- [ ] Capture the `v3` AZ list response as a frozen fixture (per Global Constraints above).
- [ ] Cross-reference every record in that fixture against an independently-known status label. Sources
      available without further live browsing: the two already-frozen `v2` `os0`/`os10` fixtures (20
      known-labeled ids from the 2026-08-05 capture, though `v2` may have since gone stale for some of
      those — treat `v2`'s *status* field as ground truth only for records whose other fields still
      match what was independently observed on the live HTML site in this session: `P505208` Active,
      `P515029`/`P508792` Pipeline). Where the HTML site itself needs consulting for additional labels
      (e.g. a few more `Closed`/`Dropped` examples beyond the ones already checked in chat this session),
      that is in scope for this task — it is still read-only, bounded verification, not a build step.
- [ ] For each candidate signal below, check whether it cleanly separates `Pipeline` from
      `Active`/`Closed`/`Dropped` across the full labeled sample:
  1. `closingdate` present vs. absent (already observed: `P515029`/`P508792` both *have* `closingdate`,
     so this alone does not separate Pipeline from Active on its own — check whether combined with
     something else it does).
  2. `curr_ibrd_commitment`/`idacommamt` present vs. absent (already observed: `P508792` lacks
     `curr_ibrd_commitment` entirely — is that IBRD-vs-IDA lending-instrument noise, or a real Pipeline
     tell? Needs more than 2 examples to know).
  3. Whether the *set* of populated fields (not any single field) forms a distinguishable pattern —
     e.g. via a simple presence-vector comparison across the labeled sample.
  4. Whether a per-project `v3` **detail** endpoint (distinct from the list endpoint) exists and carries
     a status field the list endpoint omits — check `https://search.worldbank.org/api/v3/projects/<id>`
     and any URL pattern visible in the live HTML site's own network traffic (Chrome DevTools / this
     session's `read_network_requests` tooling against `projects.worldbank.org`, not guessed).
  5. Whether cross-referencing `boardapprovaldate` against **today's date** works as a proxy despite the
     counter-example already found this session (`P508792`'s `boardapprovaldate` of 2026-08-06 is in the
     past relative to the 2026-08-12 capture date, yet the project is still `Pipeline` on the live site —
     so a future-date rule alone is already falsified; record this explicitly rather than re-deriving it
     if the same counter-example resurfaces).
- [ ] Record the outcome — which signal (if any) reliably separates Pipeline from the other three
      statuses across the sample, or the honest conclusion that the list endpoint cannot do this and a
      per-project detail call (or the HTML site's own backing API) is required per record.

**Acceptance:** A dated `docs/decisions/OPEN-QUESTIONS.md` entry stating the actual finding (working
proxy identified and what it is; or no reliable list-level proxy exists and per-record detail calls are
required; or something else found during the check) — closing the two 2026-08-12 entries' open follow-up
rather than leaving them open indefinitely. This entry is the plan's deliverable; it does not itself
authorize starting the connector migration, which is separately scoped once this is known.

**Outcome (2026-08-12):** None of candidates 1-3 were needed. Candidate 4 (per-project/detail-call
variant) resolved it, but not via a different URL path — via `read_network_requests` against the live
`projects.worldbank.org` page, the site's own JS was observed calling
`POST https://search.worldbank.org/api/v3/projects` with an explicit `fl=` (field list) query parameter
naming `status`, `projectstatusdisplay`, `last_stage_reached_name`, `proj_last_upd_date`,
`public_disclosure_date`, and ~30 other fields. Replaying that exact call from within the page (`fetch`,
`javascript_tool`) returned `status: "Pipeline"`, `last_stage_reached_name: "Concept Review"` for
`P515029` — the field was there all along, just not returned by default. Confirmed this needs no
browser session or special headers: a bare, unauthenticated `curl` against
`https://search.worldbank.org/api/v3/projects?format=json&rows=100&fl=id,project_name,status,last_stage_reached_name,boardapprovaldate,borrower,impagency,totalamt,proj_last_upd_date,public_disclosure_date&apilang=en&countrycode_exact=AZ&os=0`
(plain `GET`, no cookies) returned `total: 95`, status breakdown `{Pipeline: 2, Active: 3, Closed: 72,
Dropped: 18}`, and `P515029`/`P508792`/`P505208` all matching the live site exactly. Candidate 5's
already-falsified boardapprovaldate-vs-today heuristic is now moot — `status` itself is directly
available, no proxy needed. **Conclusion: no proxy signal is required.** The fix is `v2` → `v3` plus an
explicit `fl=` parameter that includes `status` (and, for free extra signal richness `v2` never had,
`last_stage_reached_name`/`proj_last_upd_date`/`public_disclosure_date`) — not a heuristic reconstruction
of status from other fields.

---

## Explicitly out of scope (deferred to a follow-on task, not started here)

- Rewriting `worldbank_connector.py`/`worldbank_contract.py`/`worldbank_pipeline_job.py` to call `v3`.
- Any schema/migration change to `signals`/`signal_model.py`.
- Backfilling or re-deriving already-stored `design_tender`/donor-pipeline signals against `v3` data.
- Deciding whether the existing frozen `v2` fixtures (`az_donor_pipeline_page_os0/os10.raw.json`) should
  be superseded, retired, or kept as a historical record — that is a call for whoever scopes the
  migration task, once Task 1's finding is in hand.
