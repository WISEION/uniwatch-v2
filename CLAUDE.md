# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Read this first

**`AGENTS.md` is normative and overrides convenience.** Before writing or changing any code, read it in full, plus `docs/CONTEXT.md` (condensed summary of the locked PRD/master-plan decisions). If `AGENTS.md`/`docs/CONTEXT.md` and this file ever disagree, they win.

This is a from-scratch rebuild of a legacy system ("v1" — `Tendet Watcher` / `UNIWatch`). **v1 paths are permanently off-limits**: never read, write, or reference `Documents\Tendet Watcher` or `Documents\UNIWatch` from any code/config/test/migration (docs and `_supervisor/` notes are the only allowed exception). This is enforced by `tools/check_v1_untouched.py` — run it after any change that could plausibly touch a path literal.

## Hard bans (violation = stop, no exceptions)

1. Never write to v1 (see above).
2. Never invent numbers for anything tagged `TBD-nn`/`D-nn` in the docs (financial weights, ML thresholds, SLO/RPO/RTO, permission matrix) — leave the literal `TBD-nn`/`D-nn` in place instead of substituting a "reasonable" default.
3. No silent fallback values: `missing`/`stale`/`incomplete`/`synthetic` states are always surfaced, never hidden behind a default.
4. Ingestion/derived output never overwrites a human decision — auto-derived data is always a `candidate`; only a human action creates or changes a decision.
5. BOQ (bill of quantities) is `complete` only after proven page/row reconciliation; absence of a source total is `source_exhausted_unverified`, never `complete`.
6. Green CI is not production deployment authorization — production requires a distinct approver from the initiator, in addition to CI passing.
7. No all-access role. RBAC is deny-by-default; every permission is explicit (an unknown user, disabled user, or a role with no assigned permissions all resolve to *no access*, never a default identity with access).

Every requirement ID used in commits/tests/ADRs (`FR-*`, `INV-*`, `NEG-*`, `P0xx`, `NFR-*`) must trace back to the source documents referenced in `AGENTS.md` §1 — do not invent a requirement ID.

The maker/checker and human-authority mechanics behind bans #4, #6, and #7 are spelled out in `docs/adr/0005-authority-model.md`; the synthetic/real isolation behind `packages/vendor`'s synthetic-only status (below) is `docs/adr/0004-synthetic-real-isolation.md`.

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Full test suite (unit + integration; integration spins up a real Postgres
# via testcontainers — Docker must be running). Matches CI's Full gate, which
# excludes live_network-marked tests (etender.gov.az is unreachable from
# GitHub-hosted runners; see pyproject.toml's marker doc / .github/workflows/ci.yml)
python -m pytest tests/ -q -m "not live_network"

# Single file / single test
python -m pytest tests/unit/test_pagination_and_concurrency.py -q
python -m pytest tests/integration/test_jobs_store.py::test_two_concurrent_claims_do_not_get_the_same_job -q

# v1-untouched gate (run after any change; stdlib-only, no deps needed)
python tools/check_v1_untouched.py
# first run on a machine where v1 is actually present, to record the baseline:
python tools/check_v1_untouched.py --init

# run only the live_network-marked tests (CI runs these separately, non-blocking)
python -m pytest tests/ -q -m live_network

# Run the API (dev) -- two separate services (ADR-0006)
uvicorn apps.api_tender.main:app --reload --port 8001
uvicorn apps.api_vendor.main:app --reload --port 8002

# Run the worker (dev)
python -m apps.worker.main

# Lint / format / type-check (run all four before considering a change done)
python -m ruff format --check .
python -m ruff check .
python -m mypy packages apps
python tools/check_v1_untouched.py
```

`DATABASE_URL` (SQLAlchemy async form, e.g. `postgresql+asyncpg://uniwatch:uniwatch@localhost:5432/uniwatch`) and `EXPECTED_SCHEMA_VERSION` configure `packages/platform/settings.py`; both have dev defaults.

## Architecture

**Modular monolith, except Tender/Vendor (ADR-0006):** `decision`/`algorithm`/`platform` still live in
one repo, one runtime, per ADR-0001. `tender` and `vendor` are a deliberate exception, per a customer
requirement surfaced 2026-08-05 (`docs/decisions/OPEN-QUESTIONS.md`, `docs/adr/0006-tender-vendor-service-separation.md`):
they are two independently deployable FastAPI processes (`apps/api_tender`, `apps/api_vendor`),
communicating only through a real network API contract in `packages/contracts` — never a shared
in-process import or a shared-table read across that one boundary. Business logic lives in
`packages/*`; `apps/*` are thin entry points that only wire packages to HTTP/CLI/UI — no business logic
in `apps/*`.

```
packages/platform    cross-cutting: db, migrations, RBAC, audit, correlation, errors, jobs, outbox
                      — no domain scoring/business-decision logic; shared LIBRARY imported by both
                      apps/api_tender and apps/api_vendor (not itself split into two services)
packages/tender       tender ingestion, normalization, signals
packages/vendor       vendor registry (synthetic-only until a legal gate, ADR-0004) — no Bid/No-Bid knowledge
packages/decision     Bid/No-Bid workflow, No-Go, outcomes — references immutable input *versions*, never a mutable copy
packages/algorithm    policy graph / evaluation / approval — owns policy, not business facts
packages/contracts    shared OpenAPI/DTO/schema contracts across apps/packages; for tender<->vendor
                      specifically (ADR-0006) this is a real versioned network API contract, not just
                      in-process DTOs — e.g. vendor_api.py, an httpx-based client with real
                      timeout/error handling, not a function call
apps/api_tender       FastAPI (Tender service), contract-first (OpenAPI is the source of truth),
                      request/response only
apps/api_vendor       FastAPI (Vendor service) — separate deployable process from api_tender
                      (ADR-0006), not routers on the same app
apps/worker           separate process for anything long-running: ingestion, BOQ processing,
                      reconciliation, outbox consumers — never inside an apps/api_tender or
                      apps/api_vendor request handler; not split by ADR-0006 (tender-scoped in
                      practice today, vendor has no real jobs yet)
apps/web              React/TypeScript UI (`NFR-ARC-01`) — Phase 2+ scope, not implemented yet
                      (see apps/web/README.md). Never the source of authorization truth: every
                      permission check it shows is re-verified server-side (`FR-ADM-02`)
```

Enforced import direction and domain boundaries: see `AGENTS.md` §3 and `docs/adr/0001-modular-monolith-boundaries.md` (this file already defers to `AGENTS.md` as normative, per "Read this first" above).

**Four-layer data model** (`docs/adr/0003-data-authority-and-provenance.md`) — every significant record moves through these layers, and a lower layer never overwrites a higher one:

1. Raw immutable evidence (exact source response/document, checksummed; a re-fetch creates a new snapshot, never an edit).
2. Normalized fact (typed, versioned by `parser_version`/`normalizer_version`, keeps the raw provenance link).
3. Derived signal/score (computed, versioned by the rule/model that produced it).
4. Human decision (append-only: actor, role, reason, input snapshot).

Layer 3 never writes itself as layer 4. Records also carry `data_origin` (`real`/`synthetic`/`legacy`/`derived`), `reality_status`, `freshness_status`, `completeness_status`, and distinct `captured_at`/`effective_at`/`observed_at` timestamps (never collapsed into one).

**Platform primitives already in place** (`packages/platform/`), each solving a specific v1 regression — reuse them rather than re-implementing:

- `db.py` — single `AsyncEngine` factory; `apps/api/deps.py` gives each request one connection wrapped in a transaction that commits on success / rolls back on any exception.
- `migrations_runner.py` + `migrations/*.sql` — versioned, checksummed, ledger-tracked migrations (`schema_migrations` table). Schema **never** changes as a side effect of app startup; startup only calls `assert_schema_up_to_date()` (read-only) and refuses to start on a version mismatch. Editing an already-applied migration file is a hard error (checksum mismatch) — write a new migration instead. See `migrations/README.md` for the full contract (preflight/postflight hooks, numbering convention).
- `correlation.py` — one correlation id threaded through API request → worker job → outbox row. `CorrelationIdMiddleware` is raw ASGI (not `BaseHTTPMiddleware`, which swallows exceptions before `errors.py`'s handlers see them).
- `errors.py` — every error response is the same `{"error": {code, message, correlation_id, details}}` envelope; raise `ApiError` from route/service code rather than returning ad hoc responses.
- `rbac/` — deny-by-default resolution: unknown/disabled user → `None` identity (401 via `deps.get_current_identity`); a role with zero `role_permissions` rows → empty permission set (403), never all-access.
- `jobs.py` — durable worker jobs: `SELECT ... FOR UPDATE SKIP LOCKED` claim, lease + heartbeat, checkpoint-based resume, exponential backoff retry, terminal failure after `max_attempts`. A job's identity (`job_type`/`params`/`source`/range/`correlation_id`) is fixed at enqueue and never mutated — a new range gets a new job row so a resume cursor can't leak across job identities.
- `outbox.py` — transactional outbox: `enqueue` writes in the caller's own transaction (row exists iff the effect it describes was committed); `Publisher.publish_pending` delivers at-least-once and only moves `pending` → `published`, never back.
- `idempotency.py`, `pagination.py` (opaque cursor, no offset), `concurrency.py` (If-Match / optimistic concurrency → 409) — apply these to any new mutating/paginated/listing endpoint rather than hand-rolling equivalents.
- `egress/` — every outbound HTTP call goes through `validator.py` first: scheme allowlist → `registry.py` trusted-source check → DNS resolve of *every* returned address (not just the first) → block loopback/private/link-local/metadata/CGNAT/reserved/multicast/unspecified (IPv4 and IPv6) → `fetch.py` connects to the already-checked address, never re-resolving the hostname (a TOCTOU/rebinding gap otherwise). Rejections raise typed `EgressRejected`, never a silent `None`. Do not call `httpx`/`aiohttp`/sockets directly from a connector — route through this.
- `exception_queue.py` — generic durable queue for ingestion failures that need a human or a retry (schema drift, `EgressRejected`, stale-TTL facts); a job records into it rather than swallowing or re-raising past its retry budget.
- `audit.py` — disable-not-delete + append-only audit trail: a user is disabled, never deleted, and every admin action is appended to an audit log rather than mutating history.
- `proxy.py` — `resolve_verified_peer_ip()`: `X-Forwarded-For` is attacker-controlled unless the request's immediate TCP peer is a configured trusted-proxy CIDR; rate-limit/lockout decisions must resolve the verified peer IP through this rather than trusting the header directly.

**Tender ingestion pipeline** (`packages/tender/`, spans several files): `raw_snapshot.py` saves the exact source bytes unconditionally and first — evidence capture must never depend on whether the connector currently understands the response shape. `schema_drift.py` then checks the payload against a source's frozen contract (each connector defines its own — `etender_contract.py`, `worldbank_contract.py` — as a `SourceContract` from `source_contract.py`, whose `identity_query_keys` fixes which query params define a record's identity so it's never lost to a generic canonicalizer); a drift raises `SchemaDriftDetected` and is reported via the outbox instead of being silently mapped. Only a drift-free response reaches `normalized.py`. Each external source is a fully separate connector (`etender_connector.py`, `worldbank_connector.py`, more added per `TENDER_INTELLIGENCE_SPEC.md` §5.2 as tasks require) with its own resumable-pagination job mirroring the same shape (`design_tender_job.py`, `procurement_plan_job.py`, `worldbank_pipeline_job.py`) — a job's `ingest_*` function handles exactly one already-fetched page/response and knows nothing about pagination or completeness, which live separately (`bom_lines_job.py` / `boq_completeness.py` for BOQ page/row-total reconciliation).

**Signal layer** (layer 3 of the four-layer model, built on top of normalized facts): each source has its own `Signal` builder (`signal_model.py`'s `build_donor_pipeline_signal`, `design_tender_signal.py`, `procurement_plan_signal.py`) — one builder per source, deliberately not a shared generic mapper, since fields differ too much between sources to stay honest under one abstraction. `signals_store.py` persists and queries them, including `list_signals_by_object_region()` for pulling every signal type against one real-world object. Cross-source object identity (needed for `TENDER_INTELLIGENCE_SPEC.md` §5.3's composite-trigger/intersection model) is resolved by `az_region_identity.py`'s `canonicalize_region()`, built only from region tokens actually observed in real captured data — never a hand-typed exhaustive list — so an unobserved region canonicalizes to `None` (surfaced, not guessed) rather than silently wrong.

**Vendor reputation facts** (`packages/vendor/`, SCG — Supplier Confidence Graph — 4th data layer, `TENDER_INTELLIGENCE_SPEC.md` §6.2): `reputation_model.py`'s `ReputationFact` classifies vendor event types (late delivery, quality dispute, etc.) as a typed, TTL-aware fact distinct from the vendor identity record itself; `reputation_store.py` persists them and exposes an active-facts query that respects the TTL rather than returning expired facts as if current. `synthetic_reputation.py` generates these deterministically, same synthetic/real isolation rules as the rest of `packages/vendor` (ADR-0004). The trust-coefficient formula that turns facts into a score is an open decision (`D-VND-REP`, `docs/decisions/OPEN-QUESTIONS.md`) — do not invent a weighting.

**Testing**: `tests/{unit,integration,contract,state,security,e2e,performance}` mirrors the CI gate split (`tests/README.md`) — `unit/` is pure logic (Fast gate); everything else needs real dependencies (Full gate). `tests/integration/conftest.py` spins up a session-scoped `testcontainers` Postgres container, gives each test a freshly dropped/recreated `public` schema, and applies all migrations before yielding an engine — Docker must be running locally to execute anything under `tests/integration/`.

## Working within phases

Phase/gate discipline, WORKLOG/OPEN-QUESTIONS/ADR conventions: see `AGENTS.md` §4. Plan of record for Phase 0/1: `docs/reports/PLAN-MISSION-1.md`; for the Phase 1 remainder (1.C/1.D/1.E) and the Phase 2-4 subsystems (DFE/SCG/EL/MDC), `TENDER_INTELLIGENCE_SPEC.md` (project root) supersedes `PLAN-MISSION-3/4/5.md`'s framing for the parts it covers (see `docs/CONTEXT.md` "Where things live" — it's a partial supersession, not a blanket replacement of those plan files). Check `docs/reports/WORKLOG.md`'s most recent entry for the current phase/task and whether a phase exit gate is awaiting supervisor GO before the next phase starts — do not assume this file's phase reference is still current. Likewise, `docs/decisions/OPEN-QUESTIONS.md` accumulates open decisions continuously (e.g. `D-VND-REP`, above) — treat any specific decision ID mentioned in this file as an example, not an exhaustive or current list.
