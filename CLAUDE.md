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

## Commands

```bash
# Install (editable, with dev deps)
pip install -e ".[dev]"

# Full test suite (unit + integration; integration spins up a real Postgres
# via testcontainers — Docker must be running)
python -m pytest tests/ -q

# Single file / single test
python -m pytest tests/unit/test_pagination_and_concurrency.py -q
python -m pytest tests/integration/test_jobs_store.py::test_two_concurrent_claims_do_not_get_the_same_job -q

# v1-untouched gate (run after any change; stdlib-only, no deps needed)
python tools/check_v1_untouched.py
# first run on a machine where v1 is actually present, to record the baseline:
python tools/check_v1_untouched.py --init

# Run the API (dev)
uvicorn apps.api.main:app --reload

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

**Modular monolith**: one repo, one runtime. Business logic lives in `packages/*`; `apps/{api,worker,web}` are thin entry points that only wire packages to HTTP/CLI/UI — no business logic in `apps/*`.

```
packages/platform    cross-cutting: db, migrations, RBAC, audit, correlation, errors, jobs, outbox
                      — no domain scoring/business-decision logic
packages/tender       tender ingestion, normalization, signals
packages/vendor       vendor registry (synthetic-only until a legal gate) — no Bid/No-Bid knowledge
packages/decision     Bid/No-Bid workflow, No-Go, outcomes — references immutable input *versions*, never a mutable copy
packages/algorithm    policy graph / evaluation / approval — owns policy, not business facts
packages/contracts    shared OpenAPI/DTO/schema contracts, the only sanctioned cross-package data path
apps/api              FastAPI, contract-first (OpenAPI is the source of truth), request/response only
apps/worker           separate process for anything long-running: ingestion, BOQ processing,
                      reconciliation, outbox consumers — never inside an apps/api request handler
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

**Tender ingestion pipeline** (`packages/tender/`, spans several files): `raw_snapshot.py` saves the exact source bytes unconditionally and first — evidence capture must never depend on whether the connector currently understands the response shape. `schema_drift.py` then checks the payload against the frozen contract in `etender_contract.py`; a drift raises `SchemaDriftDetected` (`schema_drift.py`) and is reported via the outbox instead of being silently mapped. Only a drift-free response reaches `normalized.py`. Resumable multi-page pagination and BOQ page/row-total reconciliation live separately in `bom_lines_job.py` / `boq_completeness.py` — `etender_connector.py`'s `ingest_*` functions each handle exactly one already-fetched page/response and know nothing about pagination or completeness.

**Testing**: `tests/{unit,integration,contract,state,security,e2e,performance}` mirrors the CI gate split (`tests/README.md`) — `unit/` is pure logic (Fast gate); everything else needs real dependencies (Full gate). `tests/integration/conftest.py` spins up a session-scoped `testcontainers` Postgres container, gives each test a freshly dropped/recreated `public` schema, and applies all migrations before yielding an engine — Docker must be running locally to execute anything under `tests/integration/`.

## Working within phases

Phase/gate discipline, WORKLOG/OPEN-QUESTIONS/ADR conventions: see `AGENTS.md` §4. Plan of record for Phase 0/1: `docs/reports/PLAN-MISSION-1.md`; for the phases after it, `TENDER_INTELLIGENCE_SPEC.md` (project root) now supersedes `PLAN-MISSION-{2..5}.md`'s framing (see `docs/CONTEXT.md` "Where things live"). Check `docs/reports/WORKLOG.md`'s most recent entry for the current phase/task and whether a phase exit gate is awaiting supervisor GO before the next phase starts — do not assume this file's phase reference is still current.
