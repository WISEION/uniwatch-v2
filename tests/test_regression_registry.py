"""Regression checklist registry (PRD Appendix A: 29 v1-audit findings +
Appendix D.2: 13 release-note defects = 42 mandatory regression tests,
G6/§9.1 PRD). Task 0.D (qa) stub requirement: every one of the 42 gets an
entry here with an explicit phase tag, per `docs/reports/PLAN-MISSION-1.md`
§2 (0.D) and §5 (traceability).

This file is a REGISTRY, not the regression test itself once a finding is
actually closed — the real test for a closed finding lives in the suite
(unit/integration/contract/state/security/e2e) that exercises it, and this
entry becomes a thin pointer to it (see P007 below) rather than a skip.
Phase tags come only from `docs/reports/PLAN-MISSION-{1..8}.md` as written;
where no PLAN-MISSION document assigns a phase yet, the entry says so
explicitly instead of guessing one (`AGENTS.md` hard ban #2: never invent a
requirement ID or a number/decision the source docs don't already contain —
the same discipline applies to inventing a phase assignment).

Do not report a `skip`-marked entry below as a passing regression test
(`tests/README.md`).
"""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Appendix A, P0 (critical) -- PLAN-MISSION-1.md §3 1.E: closed 100% in Phase 1.
# ---------------------------------------------------------------------------


def test_P001_boq_page_completeness():
    """v1: BOQ loaded only page 1; 1,644/6,288 rows lost silently. Control:
    page/row completeness proof, status only `complete` after proven
    reconciliation, `source_exhausted_unverified` if the source never
    reported a total, `incomplete` with exact missing pages if fetching
    stalls (FR-DQ-01, FR-DQ-02, FR-TND-04, INV-04). CLOSED in task 1.B --
    see `packages/tender/boq_completeness.py`,
    `tests/integration/test_boq_completeness.py` (accumulation over 3 real
    pages, `complete`/`source_exhausted_unverified`/`incomplete` states) and
    `tests/integration/test_bom_lines_pagination.py`
    (`test_resumable_pagination_processes_real_pages_in_order`, real
    reconciliation counters against the real 42-page/4135-line BOQ)."""
    # Not a stub: real regression tests live in the files named above.


def test_P002_cursor_resume_after_page_error():
    """v1: cursor skipped ahead after an error and could be reused across a
    different range. Control: atomic checkpoint + full job identity fixed at
    enqueue (FR-JOB-02, FR-JOB-04..06, INV-03). The generic mechanism is
    covered by `tests/integration/test_jobs_store.py`; the eTender-connector
    acceptance proof is CLOSED in task 1.B -- see
    `tests/integration/test_bom_lines_pagination.py`
    (`test_page_fetch_failure_resumes_same_page_not_next`: page 2 fails,
    checkpoint stays at 2, retry succeeds on the real page-2 content, page 3
    fetched next -- no skip, no duplicate; `test_new_job_identity_starts_at_page_1_independently`:
    a new job identity never inherits another job's cursor, FR-JOB-06)."""
    # Not a stub: real regression tests live in the file named above.


def test_P003_rejected_link_not_restored_by_ingestion():
    """v1: a rejected human tender<->project link was silently restored by a
    later ingestion run. Control: append-only candidate vs. human decision
    (FR-TND-08/09, DM-04, INV-01). Domain invariant only in Phase 0/1 (no
    Bid/No-Bid-adjacent linking domain exists yet). `PLAN-MISSION-1.md` §5
    [правка №1] originally assigned full closure to Phase 2, but
    `PLAN-MISSION-2.md` (which owned tender<->project linking) is now
    likely-superseded by `TENDER_INTELLIGENCE_SPEC.md` §5's own Phase 2
    content (BOQ depth + forecast layer), which does not mention linking at
    all -- **no confirmed phase as of 2026-08-05**, see
    `docs/decisions/OPEN-QUESTIONS.md` (2026-08-05 entry) for the open
    question to the owner. Not guessed here."""
    pytest.skip("no confirmed phase as of 2026-08-05 -- see docs/decisions/OPEN-QUESTIONS.md (2026-08-05 entry)")


def test_P004_confirmed_link_not_replaced_by_stronger_automatch():
    """v1: a confirmed link was silently replaced by a stronger auto-match.
    Control: ingestion cannot change an accepted link (FR-TND-09, INV-01).
    Same domain/open-phase-question as P003 above."""
    pytest.skip("no confirmed phase as of 2026-08-05 -- see docs/decisions/OPEN-QUESTIONS.md (2026-08-05 entry)")


def test_P005_final_bid_checks_active_no_go():
    """v1: an active No-Go was not checked at final Bid submission. Control:
    transactional final hard-stop (FR-DEC-05/06, INV-06). Domain invariant
    only in Phase 0/1 (Decision package does not exist yet); full closure is
    Phase 4 (`docs/reports/PLAN-MISSION-1.md` §5 [правка №1];
    `PLAN-MISSION-4.md`, draft)."""
    pytest.skip("mandatory from Phase 4 (PLAN-MISSION-1.md §5 [правка №1]; PLAN-MISSION-4.md draft)")


def test_P006_ssrf_via_redirect_or_document_link():
    """v1: SSRF via an RSS-link redirect. Control: central egress validator +
    trusted source registry, checked before DNS resolution and after every
    redirect (NFR-SEC-01..03, INV-10). CLOSED in task 1.C -- see
    `packages/platform/egress/` (registry, validator, pinned-connect fetch)
    and `tests/security/test_ssrf_suite.py`: metadata/private addresses
    blocked (loopback/RFC1918/link-local/CGNAT/NAT64, IPv4+IPv6), a 3-hop
    redirect chain to a private target rejected at the redirect step
    (never reaching the private host), DNS-rebind pinning proven, and a
    real live fetch against `etender.gov.az` succeeding end to end through
    the same validator (no false-positive block)."""
    # Not a stub: real regression tests live in the files named above.


def test_P007_orphaned_fk_rows_block_migration():
    """v1: 14 FK violations found in a local snapshot. Control: migration
    preflight scans for the invariant a migration assumes and quarantines it
    (blocks the DDL, does not silently migrate over the violation) instead
    of either succeeding silently or crashing mid-DDL (FR-DQ-06, FR-PLT-12,
    FR-PLT-13). CLOSED in task 0.D -- see
    `tests/integration/test_invariant_quarantine.py`, which also proves the
    quarantine is retryable once the underlying data is fixed."""
    # Not a stub: the real regression test lives in
    # tests/integration/test_invariant_quarantine.py. This entry is a
    # pointer for the registry, not a duplicate assertion.


# ---------------------------------------------------------------------------
# Appendix A, "High and systemic" findings.
# ---------------------------------------------------------------------------


def test_P108_details_boq_changes_visible_to_history():
    """v1: details/BOQ changes were invisible to history and notifications.
    Control: separate immutable resource versions + diff (FR-TND-05, DM-02).
    `PLAN-MISSION-2.md` (likely-superseded, see `docs/decisions/OPEN-QUESTIONS.md`
    2026-08-05) assigned this to Phase 2; `TENDER_INTELLIGENCE_SPEC.md` §5's
    own Phase 2 doesn't mention change-history/diff either -- no confirmed
    phase. The underlying versioning mechanism (immutable tender_versions,
    one row per change) is already built in 1.A/1.B; the missing piece is
    the diff/notification surface, not the storage."""
    pytest.skip("no confirmed phase as of 2026-08-05 -- see docs/decisions/OPEN-QUESTIONS.md (2026-08-05 entry)")


def test_P109_enrichment_failure_not_masked_as_success():
    """v1: an enrichment failure could read as success. Control: independent
    subresource statuses/counters (FR-TND-07). `PLAN-MISSION-2.md`
    (likely-superseded) assigned this to Phase 2 -- no confirmed phase now,
    same as P108. Substantially demonstrated already at the mechanism level
    in 1.D: `tests/integration/test_subresource_status_independence.py`
    (a failed BOQ ingestion never masks/is masked by a successful details
    ingestion for the same tender) -- not claimed as fully closed pending
    the phase question above, but not starting from zero either."""
    pytest.skip("no confirmed phase as of 2026-08-05 -- see docs/decisions/OPEN-QUESTIONS.md (2026-08-05 entry)")


def test_P110_notification_read_state_is_per_user():
    """v1: notification read-state was shared, not per-user. Control:
    per-user notification receipts (FR-NOT-01, INV-09). No PLAN-MISSION
    document yet assigns this a closing phase; partial platform
    infrastructure (append-only audit pattern) exists from 0.B, but the
    notification domain itself has not been designed."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document -- notification domain not designed yet")


def test_P111_get_notifications_is_read_only_and_idempotency_respects_deadline():
    """v1: GET on notifications wrote to the DB; dedupe ignored a changed
    deadline. Control: command/query separation + an idempotency key/
    fingerprint that changes when the request materially changes (FR-PLT-02,
    FR-PLT-03, FR-NOT-02/03). The general mechanism (fingerprint mismatch on
    a reused key -> rejected, not silently replayed) is already exercised by
    `tests/integration/test_idempotency_store.py`; the notification-specific
    acceptance proof (deadline change) has no phase assignment yet (the
    notification domain has not been designed)."""
    pytest.skip("mechanism tested (test_idempotency_store.py); notification-specific proof has no phase assigned yet")


def test_P112_reverse_proxy_uses_verified_peer_ip():
    """v1: a reverse proxy hid the real client IP, breaking lockout
    semantics. Control: trusted proxy CIDR + verified peer IP
    (FR-PLT-07). Already implemented and tested: `packages/platform/
    proxy.py`, `tests/unit/test_proxy.py`. CLOSED as a platform mechanism;
    the lockout-semantics acceptance proof it feeds is a Phase 0.B/2
    continuity item per `docs/architecture/threat-model.md` T5."""
    pytest.skip("platform mechanism closed (test_proxy.py); lockout-semantics proof continues Phase 0.B/2")


def test_P113_long_running_network_work_runs_in_worker_not_http_request():
    """v1: long network calls ran inside the HTTP request. Control: durable
    worker jobs with progress/retry/cancel/resume, never in-request
    (FR-JOB-01, FR-JOB-03). Already implemented and tested: `packages/
    platform/jobs.py`, `apps/worker/main.py`,
    `tests/integration/test_jobs_store.py`,
    `tests/integration/test_correlation_propagation.py`. CLOSED as a
    platform mechanism; the eTender-connector-specific acceptance proof is
    Phase 1."""
    pytest.skip("platform mechanism closed (test_jobs_store.py); connector-specific proof is Phase 1")


def test_P114_startup_never_migrates_schema_or_backfills():
    """v1: startup changed schema and ran backfills implicitly. Control:
    versioned migrations + ledger; startup only reads and compares versions,
    backfill is a separate explicit job (FR-PLT-12, DM-06). Already
    implemented and tested: `packages/platform/migrations_runner.py`,
    `tests/integration/test_migrations_runner.py`
    (`test_startup_check_raises_on_version_mismatch`,
    `test_startup_check_passes_when_versions_match`). CLOSED as a platform
    mechanism -- this entry is a pointer, not a stub."""


def test_P115_optimistic_concurrency_on_important_edits():
    """v1: no optimistic concurrency existed; last-write-wins. Control:
    ETag/If-Match version precondition -> 409 with current version
    (FR-PLT-04, INV-12). Already implemented and tested: `packages/
    platform/concurrency.py`, `tests/unit/test_pagination_and_concurrency.py`,
    `tests/integration/test_admin_users_api.py`
    (`test_update_with_stale_if_match_is_409_with_current_version`). CLOSED
    as a platform mechanism -- this entry is a pointer, not a stub."""


def test_P116_postgres_and_bounded_jobs_not_sqlite_process_locks():
    """v1: SQLite/process locks did not fit the target volume. Control:
    PostgreSQL from day one, bounded/leased worker jobs, measurable scaling
    (NFR-ARC-04, NFR-PRF-01/02). Structural/architectural: ADR-0002 (stack),
    `packages/platform/jobs.py`. There is no separate "regression test" for
    a stack choice beyond what already exercises Postgres+jobs
    (`tests/integration/test_jobs_store.py` runs against a real Postgres
    testcontainer); performance-budget acceptance proof (NFR-PRF-01/02
    numbers) is `TBD-01`-gated and out of Mission 1 scope."""
    pytest.skip("architectural control in place (ADR-0002); NFR-PRF numeric acceptance proof is TBD-01-gated, out of scope")


def test_P117_openapi_contract_first_strict_validation():
    """v1: no OpenAPI/strict validation; malformed input produced wrong
    behavior instead of a clean error. Control: contract-first strict
    schemas, uniform 4xx envelope (FR-PLT-01). Already implemented and
    tested: `packages/platform/errors.py`,
    `tests/unit/test_errors_and_correlation.py`
    (`test_invalid_request_body_returns_422_with_field_details`). CLOSED as
    a platform mechanism -- this entry is a pointer, not a stub."""


def test_P118_structured_observability_and_readiness():
    """v1: no structured observability/readiness. Control: correlation id,
    structured logs, liveness/readiness that reads (not writes) the ledger
    (NFR-OBS-01..03). Already implemented and tested: `packages/platform/
    correlation.py`, `packages/platform/logging.py`,
    `apps/api/routers/health.py`,
    `tests/integration/test_correlation_propagation.py`,
    `tests/unit/test_logging.py`. CLOSED as a platform mechanism; metrics/
    traces (full NFR-OBS-02) are Phase 0.B+ continuity, not yet built."""
    pytest.skip("platform mechanism closed (correlation id/logs/readiness); metrics/traces still Phase 0.B+ continuity")


def test_P119_cursor_pagination_no_offset():
    """v1: no real pagination; a project card was `1+5N`/O(N) queries.
    Control: opaque cursor pagination, no offset (FR-PLT-05/06). Already
    implemented and tested: `packages/platform/pagination.py`,
    `tests/unit/test_pagination_and_concurrency.py`,
    `tests/integration/test_admin_users_api.py`
    (`test_list_users_paginates_by_cursor_not_offset`). CLOSED as a platform
    mechanism -- this entry is a pointer, not a stub; query-budget
    enforcement per screen is Phase 2+."""


def test_P120_input_change_creates_new_review_cycle_not_overwrite():
    """v1: the workflow had no real revision cycle. Control: a changed
    critical input creates a new evaluation/review cycle rather than
    overwriting the existing case (FR-DEC-04). Stub only in Phase 0; real
    implementation is Phase 4 (`docs/reports/PLAN-MISSION-4.md` draft,
    explicitly: "P120 ... создан в Phase 0 как стаб, здесь получает реальную
    реализацию")."""
    pytest.skip("mandatory from Phase 4 (PLAN-MISSION-4.md draft) -- Decision/review-cycle domain not built yet")


# ---------------------------------------------------------------------------
# Appendix A, remaining P22x findings (frontend/UX/gates/docs/auth).
# ---------------------------------------------------------------------------


def test_P222_frontend_search_refresh_race_discards_stale_responses():
    """v1: a frontend search/refresh race let a stale response overwrite a
    newer one. Control: an abort/generation guard that discards an
    out-of-date response (FR-PLT-11). Same "partially advanced in Phase 2,
    continues Phase 3+" status as P110-P119 per `PLAN-MISSION-2.md` draft
    §5 ("P110-P120, P222 ... не входят в обязательный 100%-набор этой
    миссии, продолжаются в Phase 3+"); no PLAN-MISSION document yet names
    the phase where it becomes mandatory."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document -- no web UI exists yet (PLAN-MISSION-2.md draft)")


def test_P221_reality_provenance_quality_status_no_silent_master_import():
    """v1: a local data snapshot was insufficient as analytical truth, with
    no automatic "master" import. Control: reality/provenance/quality status
    fields on every record; no automatic master import (DM-03, DM-05,
    FR-MIG-01/02). No PLAN-MISSION document yet assigns this a closing
    phase; the four-layer data model it depends on is fixed by
    `docs/adr/0003-data-authority-and-provenance.md`, but no domain table
    exists yet to prove the acceptance criterion against."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document -- no domain table exists yet to test against")


def test_P223_deep_links_for_entity_filter_tab():
    """v1: no deep links for entity/filter/tab. Control: addressable routes,
    reload/share restore state (FR-PLT-08, FR-TND-12). `PLAN-MISSION-2.md`
    (likely-superseded, see `docs/decisions/OPEN-QUESTIONS.md` 2026-08-05)
    assigned this to Phase 2 -- no confirmed phase now; `apps/web` still
    does not exist."""
    pytest.skip("no confirmed phase as of 2026-08-05 -- see docs/decisions/OPEN-QUESTIONS.md (2026-08-05 entry)")


def test_P224_malformed_hash_does_not_break_ui_startup():
    """v1: a malformed URL hash could break UI startup. Control: strict
    route parsing/escaping + browser tests (FR-PLT-09). No PLAN-MISSION
    document yet assigns this a closing phase (`apps/web` does not exist
    yet)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document -- apps/web does not exist yet")


def test_P225_frontend_split_into_feature_domain_modules():
    """v1: one large stateful frontend module. Control: feature/domain
    modules + a typed API client (FR-PLT-10). No PLAN-MISSION document yet
    assigns this a closing phase (`apps/web` does not exist yet)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document -- apps/web does not exist yet")


def test_P226_wcag_22_aa_automated_and_keyboard_nav():
    """v1: accessibility was not checked automatically. Control: WCAG 2.2 AA,
    automated axe scan + manual keyboard-navigation check of critical flows
    (FR-UX-02). `PLAN-MISSION-2.md` (likely-superseded, see
    `docs/decisions/OPEN-QUESTIONS.md` 2026-08-05) assigned this to Phase 2
    -- no confirmed phase now; no web UI exists yet regardless."""
    pytest.skip("no confirmed phase as of 2026-08-05 -- see docs/decisions/OPEN-QUESTIONS.md (2026-08-05 entry)")


def test_P227_release_gate_covers_all_critical_failure_classes():
    """v1: the release gate did not cover all critical failure classes.
    Control: layered gates -- state/security/data/browser/migration (PRD
    §9.1, §9.2). Cumulative: this repo's gate coverage grows with every
    phase (0.D wires Fast/Full; RC/production gates are Phase 6). No single
    phase "closes" this finding -- it is re-evaluated at every gate-adding
    task; tracked here so it is not silently dropped from the registry."""
    pytest.skip("cumulative across phases -- re-evaluated as each gate is added, not closed by a single phase")


def test_P228_docs_and_graphify_checked_against_source_not_drifting():
    """v1: documentation and the Graphify knowledge graph drifted from the
    real system. Control: a docs/ADR gate; Graphify checked against sources
    (NFR-DOC-01/02). No PLAN-MISSION document yet assigns this a closing
    phase or names the specific CI check; `AGENTS.md` already enforces the
    docs-first/ADR discipline by convention, but no automated drift-check
    exists yet."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document -- no automated docs-drift check exists yet")


def test_P229_auth_session_proxy_deploy_db_contracts_explicit():
    """v1: thin auth/operations mismatches (password version, OIDC binding,
    sign-out, proxy config, DB rollback compatibility). Control: explicit
    auth/session/proxy/deploy/DB-compatibility contracts (NFR-SEC-06,
    NFR-REL-03, INT-04). Blocked on `D-IDP` (real IdP decision) for the
    auth/session parts; proxy contract already covered by P112 above. No
    PLAN-MISSION document yet assigns a single closing phase for the full
    set (auth/session parts land around Phase 6 per `docs/CONTEXT.md`
    D-IDP)."""
    pytest.skip("auth/session parts blocked on D-IDP (~Phase 6); proxy part already covered by P112 (test_proxy.py)")


# ---------------------------------------------------------------------------
# Appendix D.2 -- 13 release-note defects (RN-01..13). None of these are
# mentioned by phase in any PLAN-MISSION document yet (checked against
# PLAN-MISSION-1..8.md) -- every entry below says so explicitly rather than
# guessing a phase.
# ---------------------------------------------------------------------------


def test_RN01_per_source_scan_status_not_aggregated():
    """v1 0.11.0: one failed source marked all sources' scan status failed.
    Control: per-source scan events (FR-DQ-05)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN02_host_unavailability_not_masked_as_policy_denial():
    """v1 0.11.0: a host being unreachable was masked as a robots.txt denial,
    suppressing retry -- "decision" and "failure" were conflated. Control:
    retry only for failures; a denial is a terminal decision (FR-JOB-03)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN03_restart_does_not_re_enable_operator_disabled_sources():
    """v1 0.11.0: a restart re-enabled sources an operator had disabled.
    Control: seed/deploy never overwrites operator-set fields (INV-01
    extended to configuration)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN04_cost_parser_does_not_take_first_number_as_the_value():
    """v1 0.11.7: the cost parser took the first number after "AZN"
    ("2.5 billion" -> 2.5). Control: prose never reaches a hard stop
    (FR-DEC-05, §5.6)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN05_every_tender_belongs_to_a_client():
    """v1 0.11.5: 0/103 tenders had a client; approving a candidate created a
    client without linking the tenders that produced it. Control: invariant
    "every tender belongs to a client" (FR-TND-08, INT-01)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN06_url_canonicalization_preserves_identity_query_keys():
    """v1 0.19.0: URL canonicalization dropped the whole query string,
    silently merging distinct articles differing only by `?newsID=N`.
    Control: `identity_query_keys` in the source contract (INT-02).
    Explicitly assigned to Phase 1 task 1.A in `PLAN-MISSION-1.md` §2
    ("identity_query_keys в контракте источника ... урок RN-06"). CLOSED --
    see `packages/tender/source_contract.py` (`canonical_identity`) and
    `tests/unit/test_source_contract.py`
    (`test_canonical_identity_distinguishes_records_a_naive_canonicalizer_would_merge`,
    `test_canonical_identity_uses_all_identity_query_keys_for_paged_resources`)."""
    # Not a stub: real regression tests live in the file named above.


def test_RN07_removed_source_reconciled_with_db_not_left_enabled_forever():
    """v1 0.20.0: a source removed from config stayed enabled in the DB
    forever. Control: config<->DB reconciliation on every deploy."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN08_decisions_ordered_monotonically_not_by_uuid4():
    """v1 0.13.0: decisions were ordered by uuid4 (not monotonic); a No-Go
    could "beat" a later Go in the same second. Control: monotonic decision
    ordering (FR-DEC-04, INV-06)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN09_new_user_role_select_has_no_dangerous_preselected_default():
    """v1 0.16.0: the new-user role select preselected `system_admin` as the
    first option. Control: no accidental dangerous default (FR-ADM-03)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN10_permission_disabled_controls_are_visually_distinct():
    """v1 0.16.0: permission-disabled controls looked identical to active
    ones -- the permission worked, but the signal was invisible. Control:
    explicit `:disabled` UI states (§9.2 UX acceptance)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN11_version_bump_has_a_single_source_of_truth():
    """v1 0.10.3: a version bump touched 4 code surfaces but only 2 were
    documented -- the gate failed minutes later, not immediately. Control: a
    single version source, checked in the Fast gate."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN12_production_deploy_requires_active_required_reviewer():
    """v1 0.10.2->0.10.4: `environment: production` had no active required
    reviewer on the private plan -- one person could deploy alone. Control:
    INV-14 enforced inside the workflow itself, not only platform settings
    (INV-14)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")


def test_RN13_scheduler_state_is_an_explicit_field_not_inferred_from_zero():
    """v1 0.11.1: `/api/source-health` showed `default_interval_minutes: 0`
    as normal even when the scheduler was disabled. Control: scheduler state
    is its own explicit field (NFR-OBS-03)."""
    pytest.skip("no phase assigned yet in any PLAN-MISSION document")
