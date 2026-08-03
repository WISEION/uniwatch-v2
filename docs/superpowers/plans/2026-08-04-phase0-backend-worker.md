# Phase 0, task 0.B — backend-core + worker-connector — Implementation Plan

**Goal:** Build the FastAPI contract-first skeleton (`apps/api` + `packages/platform`) and the
durable worker skeleton (`apps/worker` + shared job/outbox primitives in `packages/platform`),
each proving the platform conventions the rest of the system will rely on.

**Architecture:** One Python project (single `pyproject.toml`, single venv) shared by
`apps/api`, `apps/worker`, and `packages/*`, per the modular-monolith boundary in
`docs/adr/0001-modular-monolith-boundaries.md`. `packages/platform` holds cross-cutting
mechanisms (RBAC, idempotency, pagination, concurrency, logging, migrations runner, job/outbox
primitives) — no domain logic. `apps/api` wires those mechanisms to HTTP for one concrete
platform-domain resource (`admin/users` — permissions/roles/disable, which *is* platform
domain per `AGENTS.md` §5, not tender/vendor/decision). `apps/worker` wires the job primitives
to a standalone process with one example job type that proves restart-survival.

**Tech Stack:** FastAPI, Pydantic v2, SQLAlchemy 2.0 (async core, `asyncpg` driver), PostgreSQL
(via `testcontainers` for integration tests — no local server, no SQLite substitution per
`NEG-01` spirit), pytest + pytest-asyncio + httpx (ASGI transport) + hypothesis not required
here.

## Global constraints

- No SQLite fallback (migrations/README + WORKLOG note NEG-01 spirit). Integration tests use
  `testcontainers[postgres]`, real docker (confirmed available: `docker ps` works locally).
- Dependencies minimal and version-pinned in `pyproject.toml`.
- Every requirement ID used in code/tests/commits must trace to PRD/master-plan (AGENTS.md §1).
- No TBD numbers substituted (backoff schedule constants use small fixed values documented as
  skeleton defaults — not TBD-tagged financial/SLO numbers, so this is fine — but do not invent
  SLO-looking thresholds framed as decisions).
- `packages/tender`, `packages/vendor`, `packages/decision`, `packages/algorithm` are **not**
  touched — out of scope for 0.B.
- Do not implement 0.C (security review/egress validator impl) or 0.D (CI gates, regression
  stubs) — stop after 0.B, per supervisor task-003.

---

## File structure

```
pyproject.toml
.python-version (optional)
packages/platform/
  __init__.py
  settings.py            env-based config (DB DSN, trusted proxy CIDRs, schema version)
  logging.py             structured JSON logging + correlation id filter
  correlation.py          correlation-id contextvar + ASGI middleware
  errors.py               error envelope model + FastAPI exception handlers
  db.py                    async engine/session factory
  migrations_runner.py     ledger reader/applier (FR-PLT-12)
  idempotency.py           idempotency key store + FastAPI dependency (FR-PLT-03)
  pagination.py            opaque cursor encode/decode (FR-PLT-05)
  concurrency.py           ETag/version precondition helper (FR-PLT-04)
  proxy.py                 trusted CIDR + verified peer IP (FR-PLT-07)
  rbac/
    __init__.py
    models.py              Permission/Role/RoleAssignment dataclasses
    dependency.py           require_permission() deny-by-default FastAPI dependency
  audit.py                  audit log write helper (FR-ADM-05)
  jobs.py                   Job model + JobStore (claim/lease/checkpoint/retry/cancel) (FR-JOB-01..03)
  outbox.py                 transactional outbox enqueue + publisher (FR-JOB-07)
apps/api/
  __init__.py
  main.py                  app factory: middleware, exception handlers, routers, OpenAPI
  deps.py                  DB session dep, dev-identity dep (header-based, D-IDP stub)
  routers/
    health.py               liveness/readiness (FR-PLT-... / NFR-OBS-01/03)
    admin_users.py           POST/GET/PATCH/POST-disable demonstrating all conventions
apps/worker/
  __init__.py
  main.py                  worker loop entry point
  example_job.py            example job type (paged_echo) proving lease/resume/backoff
migrations/
  0001_platform_core.sql    users/roles/permissions/role_permissions/idempotency_keys/audit_log
  0002_platform_jobs.sql     jobs/outbox tables
tests/unit/
  test_pagination.py
  test_concurrency.py
  test_proxy.py
  test_rbac_dependency.py
  test_idempotency_store.py (fake/in-memory transport where feasible)
  test_jobs_store.py (may require DB — see integration split)
tests/integration/
  conftest.py               testcontainers postgres fixture, migrated schema
  test_admin_users_api.py    idempotency/cursor/ETag/RBAC/disable end-to-end over HTTP
  test_migrations_runner.py  ledger apply + startup mismatch failure
  test_job_lease_resume.py   FR-JOB-01..03, P113
  test_outbox_transactional.py FR-JOB-07
  test_correlation_propagation.py NFR-OBS-01
```

## Interfaces (so later tasks don't guess signatures)

- `packages/platform/correlation.py`: `get_correlation_id() -> str`, `CorrelationIdMiddleware`
  (ASGI), header name `X-Correlation-Id` (accepted if present, else generated).
- `packages/platform/errors.py`: `ErrorEnvelope(error: ErrorDetail)`, `ErrorDetail(code: str,
  message: str, correlation_id: str, details: list[dict] | None)`. Registered via
  `install_error_handlers(app: FastAPI)`.
- `packages/platform/db.py`: `get_engine(settings) -> AsyncEngine`, `session_scope(engine) ->
  AsyncIterator[AsyncConnection]`.
- `packages/platform/migrations_runner.py`: `MigrationRunner(engine, migrations_dir)`,
  `.pending() -> list[Migration]`, `.apply_all() -> list[AppliedMigration]`,
  `.current_version(conn) -> int | None`.
- `packages/platform/idempotency.py`: `class IdempotencyStore`, `.get_or_reserve(conn, key,
  route, fingerprint) -> IdempotencyRecord | None` (None = new reservation, caller proceeds;
  non-None = replay, caller returns stored response). `.store_response(conn, key, status,
  body)`.
- `packages/platform/pagination.py`: `encode_cursor(sort_key: tuple) -> str`,
  `decode_cursor(cursor: str) -> tuple`, both opaque base64, no offset semantics anywhere.
- `packages/platform/concurrency.py`: `check_precondition(if_match: str | None, current_version:
  int) -> None` (raises `PreconditionFailed` -> 409 with `current_version`/diff payload).
- `packages/platform/rbac/dependency.py`: `require_permission(permission: str) ->
  Callable[..., Awaitable[Identity]]` — FastAPI dependency; raises 403 if `permission` not in
  the caller's resolved permission set. Deny-by-default: unknown role/no assignment = empty
  permission set.
- `packages/platform/proxy.py`: `resolve_verified_peer_ip(request: Request, trusted_cidrs:
  list[str]) -> str` — returns `request.client.host` unless it is within a trusted CIDR, in
  which case it trusts the right-most untrusted-hop entry in `X-Forwarded-For`.
- `packages/platform/jobs.py`: `JobIdentity(job_type, params, source, range_start, range_end,
  contract_version, correlation_id)`, `JobStore.enqueue(conn, identity) -> job_id`,
  `.claim(conn, worker_id, lease_seconds) -> Job | None`, `.heartbeat(conn, job_id, worker_id,
  lease_seconds)`, `.checkpoint(conn, job_id, checkpoint: dict)`, `.complete(conn, job_id)`,
  `.fail_retry(conn, job_id, error: str, backoff_seconds: int)`, `.cancel(conn, job_id)`.
- `packages/platform/outbox.py`: `enqueue(conn, aggregate_type, aggregate_id, event_type,
  payload, correlation_id)` (same transaction as caller), `Publisher.publish_pending(conn) ->
  list[OutboxEvent]` (idempotent — marks `published_at`, safe to re-run).

## Task breakdown (implementation order, TDD per key mechanism)

1. **Bootstrap**: `pyproject.toml`, venv, `pip install -e .[dev]`. Deliverable: `pytest
   --collect-only` runs (even with zero tests).
2. **Migrations**: `0001_platform_core.sql`, `0002_platform_jobs.sql`,
   `migrations_runner.py` + `test_migrations_runner.py` (empty DB apply, re-run no-op,
   mismatch-at-startup failure). Requires testcontainers fixture — build `conftest.py` here.
3. **Logging/correlation/errors**: unit tests for correlation id generation/propagation and
   error envelope shape; wire into a bare `FastAPI()` app in a test only (not yet `apps/api`).
4. **Idempotency/pagination/concurrency**: unit tests per helper (pure functions / DB-backed
   store against testcontainers).
5. **RBAC + disable-not-delete + audit**: unit tests for deny-by-default resolution; DB-backed
   test for disable-not-delete (row stays, `status='disabled'`, audit row written).
6. **Trusted proxy / verified peer IP**: pure unit tests, no DB (P112 regression: spoofed XFF
   from an untrusted peer does not change resolved IP).
7. **apps/api wiring**: `main.py`, `deps.py`, `routers/health.py`, `routers/admin_users.py`.
   Integration test drives the full HTTP surface: create (idempotent), list (cursor), patch
   (ETag), disable (audit), permission-denied paths (403 deny-by-default).
   → **commit backend-core** here.
8. **Jobs + outbox** in `packages/platform`: TDD `test_job_lease_resume.py` (claim → checkpoint
   → simulate crash (drop lease, don't complete) → new claim resumes from checkpoint, not from
   scratch, not skipping ahead) and `test_outbox_transactional.py` (effect + outbox row same
   transaction; publisher re-run is a no-op for already-published rows).
9. **apps/worker wiring**: `main.py` loop, `example_job.py`. Integration test:
   `test_correlation_propagation.py` — enqueue via a fake "API" call carrying a correlation id,
   worker log line and outbox row both carry the same id.
   → **commit worker-connector** here.
10. **Full verification pass**: run entire suite, capture output, fix failures.
11. **WORKLOG append + stop.**

## Self-review notes

- Spec coverage checked against supervisor task-003 items 1-9: all nine map to a task above
  (1→3, 2→4, 3→5/6, 4→7, 5→3/7, 6→9, 7→8, 8→8, 9→9).
- No placeholders: every interface above has a concrete signature; SQL migrations will be
  written in full in task 2, not stubbed.
- Postgres-only: if testcontainers cannot pull/start an image (network/docker restriction),
  integration tests are marked `skip` with the reason recorded, and the blocker goes in
  WORKLOG — never silently swapped to SQLite.
