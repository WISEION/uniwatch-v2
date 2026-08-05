# apps/api → apps/api_tender + apps/api_vendor split (ADR-0006) Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement ADR-0006 — split the single `apps/api` FastAPI app into two independently
deployable processes, `apps/api_tender` and `apps/api_vendor`, and prove they communicate over a real
network API contract (`packages/contracts`), not an in-process function call.

**Architecture:** `apps/api_tender` is a straight rename of everything currently in `apps/api` (no
behavior change — there is no tender/vendor business-logic HTTP surface yet, only platform-level
health/admin_users routes). `apps/api_vendor` is a new, minimal FastAPI app skeleton exposing exactly
one real endpoint (`GET /internal/ping`) that proves the pattern. `packages/contracts` gets its first
real code: a Pydantic response schema + an `httpx`-based async client that calls `/internal/ping` over
real HTTP, forwarding the caller's ambient correlation id as the `X-Correlation-Id` header (the shared
`CorrelationIdMiddleware` in `packages/platform/correlation.py` already reads that header on the
receiving side — confirmed by reading its source, no changes needed there).

**Tech Stack:** Python 3.12, FastAPI, `httpx` (already a dependency; `httpx.ASGITransport` and
`httpx.MockTransport` are both built into `httpx`, no new dependency needed), pytest + pytest-asyncio,
testcontainers Postgres (via `tests/conftest.py`'s `engine`/`_database_url` fixtures, available
repo-wide since `conftest.py` lives at `tests/conftest.py`, not scoped to one subdirectory).

## Global Constraints

- **No real vendor business logic invented.** `packages/vendor` stays empty — the one new
  `apps/api_vendor` endpoint (`GET /internal/ping`) returns a static `{"service": "vendor", "status":
  "ok"}`, not fabricated vendor data. Inventing fake vendor records here would violate this repo's hard
  ban on fabricating facts.
- **`/internal/ping` is deliberately unauthenticated** (like `/health/live`) — real service-to-service
  auth is explicitly deferred by ADR-0006 to the still-open `D-IDP`/`D-HOST` decisions. This gap must be
  recorded in `docs/decisions/OPEN-QUESTIONS.md` (Task 6), not silently assumed secure.
- **No database/CI/CD/hosting-topology decisions.** Both new apps may share one PostgreSQL instance for
  now (unchanged) — do not invent a database-per-service answer; that is tied to the still-open
  `TBD-05`/`D-HOST` (see ADR-0006).
- **`apps/worker` is not touched by this plan** — ADR-0006 defers any worker split until real vendor
  ingestion work starts.
- **Every commit lands via a feature branch + PR + green CI**, not a direct push to `master` — GitHub
  branch protection requires Fast gate + Full gate to pass first (see `docs/decisions/OPEN-QUESTIONS.md`,
  2026-08-05, "etender.gov.az confirmed unreachable..." entry, for how this was set up).
- Every requirement ID used must trace to `ADR-0006`, `NFR-OBS-01`, `NFR-ARC-05/06`, or `FR-PLT-01`
  (all already-existing IDs) — do not invent a new one.

---

## Task 1: Rename `apps/api` → `apps/api_tender`

**Files:**
- Move: `apps/api/__init__.py` → `apps/api_tender/__init__.py`
- Move: `apps/api/main.py` → `apps/api_tender/main.py` (content unchanged)
- Move: `apps/api/deps.py` → `apps/api_tender/deps.py` (content unchanged)
- Move: `apps/api/routers/__init__.py` → `apps/api_tender/routers/__init__.py`
- Move: `apps/api/routers/health.py` → `apps/api_tender/routers/health.py` (content unchanged)
- Move: `apps/api/routers/admin_users.py` → `apps/api_tender/routers/admin_users.py` (content unchanged)
- Modify: `apps/api/README.md` → move to `apps/api_tender/README.md`, update its one line of prose
- Move: `tests/integration/test_health.py` → `tests/integration/test_api_tender_health.py`
- Modify: `tests/integration/test_admin_users_api.py` (import path only)
- Modify: `.github/workflows/ci.yml` (Fast gate's "API schema validates" step)
- Modify: `packages/platform/migrations_runner.py`, `packages/platform/rbac/dependency.py` (docstring
  path references only, no behavior change)
- Modify: `tests/test_regression_registry.py` (docstring path reference, line ~237)

**Interfaces:**
- Produces: `apps.api_tender.main.create_app(settings=None) -> FastAPI` and `apps.api_tender.main.app`
  — identical signature/behavior to the old `apps.api.main.create_app`/`apps.api.main.app`, just a new
  import path. Later tasks (2-5) don't consume this directly, but Task 6's CI step does.

- [ ] **Step 1: Move the directory**

```bash
git mv apps/api apps/api_tender
git mv apps/api_tender/README.md apps/api_tender/README.md.tmp  # placeholder, edited next step
mv apps/api_tender/README.md.tmp apps/api_tender/README.md
```

(The `git mv apps/api apps/api_tender` alone moves every file inside, including `README.md` — the
extra two lines above are not needed; just run `git mv apps/api apps/api_tender`.)

- [ ] **Step 2: Update `apps/api_tender/README.md`**

Replace its content:

```markdown
# apps/api_tender

FastAPI entry point for the **Tender** service (ADR-0006: Tender and Vendor are separate deployable
processes, not one monolith app — see `apps/api_vendor` for the other side). Contract-first: OpenAPI is
the source of truth, strict request/response validation (`FR-PLT-01`). Wires `packages/platform`,
`packages/tender`, etc. to HTTP — no business logic lives here (see
`docs/adr/0001-modular-monolith-boundaries.md`, `docs/adr/0006-tender-vendor-service-separation.md`).

Run: `uvicorn apps.api_tender.main:app --reload --port 8001`
```

Save as `apps/api_tender/README.md`.

- [ ] **Step 3: Move and update the health test**

```bash
git mv tests/integration/test_health.py tests/integration/test_api_tender_health.py
```

In `tests/integration/test_api_tender_health.py`, change the one import line:

```python
from apps.api_tender.main import create_app
```

(was `from apps.api.main import create_app`; nothing else in the file changes.)

- [ ] **Step 4: Update `tests/integration/test_admin_users_api.py`**

Read the file first, then change its `from apps.api.main import create_app` (or equivalent) import to:

```python
from apps.api_tender.main import create_app
```

Do not change anything else in the file.

- [ ] **Step 5: Run the moved/updated tests to confirm nothing broke**

Run: `python -m pytest tests/integration/test_api_tender_health.py tests/integration/test_admin_users_api.py -v`
Expected: all PASS, same as before the rename (this is a pure import-path change, no behavior change).

- [ ] **Step 6: Update `.github/workflows/ci.yml`'s Fast gate**

Read the file first. Replace the "API schema validates" step:

```yaml
      # Contract-first sanity check (FR-PLT-01): the OpenAPI schema each app
      # actually serves must build without error. Does not need a DB --
      # both apps create their engine lazily (see apps/api_tender/main.py's
      # and apps/api_vendor/main.py's module docstrings).
      - name: API schemas validate (tender + vendor)
        run: |
          python -c "
          from apps.api_tender.main import app as tender_app
          from apps.api_vendor.main import app as vendor_app
          for name, app in [('tender', tender_app), ('vendor', vendor_app)]:
              schema = app.openapi()
              assert schema['paths'], f'{name} OpenAPI schema has no paths'
              print(f'{name} OpenAPI OK: {len(schema[\"paths\"])} path(s)')
          "
```

(This step will fail until Task 2 creates `apps/api_vendor` — that's expected and fine; Task 1's own
test-passing criterion is Step 5 above, run locally. The CI file change is committed now so Task 2's
commit doesn't need to touch `ci.yml` again.)

- [ ] **Step 7: Update docstring-only path references (no behavior change)**

In `packages/platform/migrations_runner.py`, change the comment mentioning `apps/api/main.py` to
`apps/api_tender/main.py` (and note `apps/api_vendor/main.py` too, since both now apply):

```python
#   fixture, never by apps/api_tender/main.py, apps/api_vendor/main.py, or apps/worker/main.py.
```

In `packages/platform/rbac/dependency.py`, change the comment mentioning `apps/api/deps.py` to
`apps/api_tender/deps.py` (this dependency pattern only exists in the tender app for now — vendor has
no authenticated routes yet, see Task 2's constraints).

In `tests/test_regression_registry.py`, change the docstring line `apps/api/routers/health.py` to
`apps/api_tender/routers/health.py, apps/api_vendor/routers/health.py` (both apps now have their own
health router after Task 2).

- [ ] **Step 8: Commit**

```bash
git add -A
git commit -m "refactor(api): rename apps/api to apps/api_tender (ADR-0006, task 1/6)"
```

---

## Task 2: `apps/api_vendor` skeleton with its own health check

**Files:**
- Create: `apps/api_vendor/__init__.py`
- Create: `apps/api_vendor/main.py`
- Create: `apps/api_vendor/routers/__init__.py`
- Create: `apps/api_vendor/routers/health.py`
- Create: `apps/api_vendor/README.md`
- Test: `tests/integration/test_api_vendor_health.py`

**Interfaces:**
- Produces: `apps.api_vendor.main.create_app(settings=None) -> FastAPI`, `apps.api_vendor.main.app`.
  Task 3 adds a router to this same `main.py`. Task 6's CI step (already written in Task 1) imports
  `apps.api_vendor.main.app`.

- [ ] **Step 1: Write the failing test**

```python
"""NFR-OBS-01, NFR-OBS-03, FR-PLT-12 -- apps/api_vendor's own health check,
independent of apps/api_tender (ADR-0006: separate deployable services)."""

from __future__ import annotations

import httpx
import pytest_asyncio

from apps.api_vendor.main import create_app
from packages.platform.settings import Settings


@pytest_asyncio.fixture
async def client(engine, _database_url, migrated_asyncpg_dsn):
    settings = Settings(database_url=_database_url, expected_schema_version=8)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as c:
        yield c


async def test_liveness_is_always_ok(client):
    response = await client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


async def test_readiness_ok_when_schema_matches(client):
    response = await client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "ok"
    assert body["schema_version"] == 8
```

Save as `tests/integration/test_api_vendor_health.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_api_vendor_health.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'apps.api_vendor'`.

- [ ] **Step 3: Write `apps/api_vendor/__init__.py`** (empty file)

- [ ] **Step 4: Write `apps/api_vendor/routers/__init__.py`** (empty file)

- [ ] **Step 5: Write `apps/api_vendor/routers/health.py`**

```python
"""Liveness/readiness for the Vendor service (NFR-OBS-01, NFR-OBS-03,
FR-PLT-12) -- independent of apps/api_tender's own health router
(ADR-0006: separate deployable services, each reports its own readiness).
Readiness reads the migration ledger and dependency connectivity -- it
never applies migrations (FR-PLT-12 rule 1)."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Request
from pydantic import BaseModel

from packages.platform.errors import ApiError
from packages.platform.migrations_runner import MigrationRunner

router = APIRouter(tags=["health"])

MIGRATIONS_DIR = Path(__file__).resolve().parents[3] / "migrations"


class LivenessResponse(BaseModel):
    status: str


class ReadinessResponse(BaseModel):
    status: str
    schema_version: int
    expected_schema_version: int


@router.get("/health/live", response_model=LivenessResponse)
async def liveness() -> LivenessResponse:
    return LivenessResponse(status="ok")


@router.get("/health/ready", response_model=ReadinessResponse)
async def readiness(request: Request) -> ReadinessResponse:
    settings = request.app.state.settings
    runner = MigrationRunner(settings.asyncpg_dsn, MIGRATIONS_DIR)
    try:
        current = await runner.current_version()
    except Exception as exc:
        raise ApiError(status_code=503, code="not_ready", message=f"database unreachable: {exc}") from exc

    if current is None or current != settings.expected_schema_version:
        raise ApiError(
            status_code=503,
            code="not_ready",
            message="schema version mismatch",
            details=[{"expected": settings.expected_schema_version, "actual": current}],
        )
    return ReadinessResponse(
        status="ok",
        schema_version=current,
        expected_schema_version=settings.expected_schema_version,
    )
```

Save as `apps/api_vendor/routers/health.py`. (This is a copy of `apps/api_tender/routers/health.py` —
duplication is intentional here: each service must be independently readiness-checkable without
importing the other service's router module, matching ADR-0006's "own process" requirement.)

- [ ] **Step 6: Write `apps/api_vendor/main.py`**

```python
"""FastAPI app factory for the Vendor service (ADR-0006: Tender and Vendor
are separate deployable processes, not routers on one app -- see
apps/api_tender/main.py for the other side). Same shape as
apps/api_tender/main.py: OpenAPI is the source of truth, strict validation,
unified error envelope, correlation id (FR-PLT-01, P117)."""

from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from packages.platform.correlation import CorrelationIdMiddleware
from packages.platform.db import get_engine
from packages.platform.errors import install_error_handlers
from packages.platform.logging import configure_logging
from packages.platform.settings import Settings, get_settings

from .routers import health


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or get_settings()
    configure_logging()

    # Engine created eagerly, not in lifespan (see apps/api_tender/main.py's
    # identical rationale: ASGITransport-based tests don't send lifespan
    # protocol events).
    engine = get_engine(settings.database_url)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        yield
        await engine.dispose()

    app = FastAPI(title="UNIWatch v2 API — Vendor", lifespan=lifespan)
    app.state.settings = settings
    app.state.engine = engine
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)
    app.include_router(health.router)
    return app


app = create_app()
```

Save as `apps/api_vendor/main.py`.

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_api_vendor_health.py -v`
Expected: both PASS.

- [ ] **Step 8: Write `apps/api_vendor/README.md`**

```markdown
# apps/api_vendor

FastAPI entry point for the **Vendor** service (ADR-0006: Tender and Vendor are separate deployable
processes — see `apps/api_tender` for the other side). Contract-first: OpenAPI is the source of truth
(`FR-PLT-01`). `packages/vendor` has no domain code yet (synthetic-only, pre-legal-gate) — this app is
currently a skeleton plus one proof endpoint (`GET /internal/ping`, see
`docs/adr/0006-tender-vendor-service-separation.md`), not real vendor business logic.

Run: `uvicorn apps.api_vendor.main:app --reload --port 8002`
```

Save as `apps/api_vendor/README.md`.

- [ ] **Step 9: Commit**

```bash
git add apps/api_vendor tests/integration/test_api_vendor_health.py
git commit -m "feat(api): apps/api_vendor skeleton with its own health check (ADR-0006, task 2/6)"
```

---

## Task 3: `GET /internal/ping` on `apps/api_vendor`

**Files:**
- Create: `apps/api_vendor/routers/internal.py`
- Modify: `apps/api_vendor/main.py` (register the new router)
- Test: `tests/integration/test_api_vendor_health.py` (add one test to the existing file)

**Interfaces:**
- Produces: `GET /internal/ping` → `{"service": "vendor", "status": "ok"}`, HTTP 200, unauthenticated.
  Task 4's `packages/contracts/vendor_api.py` calls this exact path and expects this exact JSON shape.

- [ ] **Step 1: Write the failing test**

Append to `tests/integration/test_api_vendor_health.py`:

```python
async def test_internal_ping_is_unauthenticated_and_static(client):
    # Deliberately unauthenticated (ADR-0006 defers real service-to-service
    # auth to D-IDP/D-HOST) and deliberately static, not real vendor data
    # (packages/vendor has no domain code yet) -- this endpoint exists only
    # to prove the tender<->vendor API contract mechanism.
    response = await client.get("/internal/ping")
    assert response.status_code == 200
    assert response.json() == {"service": "vendor", "status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_api_vendor_health.py::test_internal_ping_is_unauthenticated_and_static -v`
Expected: FAIL with `404 != 200` (route doesn't exist yet).

- [ ] **Step 3: Write `apps/api_vendor/routers/internal.py`**

```python
"""Internal, service-to-service endpoints for the Vendor service (ADR-0006).
`GET /internal/ping` is deliberately trivial and unauthenticated -- it
proves the tender<->vendor real-API-contract mechanism (packages/contracts)
works end to end, without inventing real vendor business data
(packages/vendor has no domain code yet, synthetic-only pre-legal-gate).

Deliberately UNAUTHENTICATED: real service-to-service auth is deferred by
ADR-0006 to the still-open D-IDP/D-HOST decisions -- recorded as an open
gap in docs/decisions/OPEN-QUESTIONS.md, not silently assumed secure. Any
future /internal/* endpoint carrying real data must not copy this
unauthenticated pattern without first closing that gap."""

from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter(tags=["internal"])


class PingResponse(BaseModel):
    service: str
    status: str


@router.get("/internal/ping", response_model=PingResponse)
async def ping() -> PingResponse:
    return PingResponse(service="vendor", status="ok")
```

Save as `apps/api_vendor/routers/internal.py`.

- [ ] **Step 4: Register the router in `apps/api_vendor/main.py`**

Change:

```python
from .routers import health
```

to:

```python
from .routers import health, internal
```

and change:

```python
    app.include_router(health.router)
```

to:

```python
    app.include_router(health.router)
    app.include_router(internal.router)
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_api_vendor_health.py -v`
Expected: all PASS (3 tests: liveness, readiness, internal ping).

- [ ] **Step 6: Commit**

```bash
git add apps/api_vendor tests/integration/test_api_vendor_health.py
git commit -m "feat(api): GET /internal/ping proof endpoint on apps/api_vendor (ADR-0006, task 3/6)"
```

---

## Task 4: `packages/contracts/vendor_api.py` — the real network API contract

**Files:**
- Create: `packages/contracts/vendor_api.py`
- Test: `tests/unit/test_vendor_api_contract.py`

**Interfaces:**
- Consumes: nothing from earlier tasks at import time (this is a pure client module) — but its
  behavior is proven against the real `apps.api_vendor.main` app in Task 5.
- Produces: `class VendorPingResponse(BaseModel)` with fields `service: str`, `status: str`;
  `class VendorApiError(Exception)`; `async def ping_vendor_service(base_url: str, *, correlation_id:
  str | None = None, client: httpx.AsyncClient | None = None) -> VendorPingResponse`.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for packages/contracts/vendor_api.py -- the real network API
contract between apps/api_tender and apps/api_vendor (ADR-0006). Pure unit
tests: httpx.MockTransport stands in for a real vendor service, no DB, no
real network, no real apps/api_vendor app needed here (that end-to-end
proof is tests/contract/test_tender_vendor_contract.py)."""

from __future__ import annotations

import httpx
import pytest

from packages.contracts.vendor_api import VendorApiError, VendorPingResponse, ping_vendor_service
from packages.platform.correlation import bind_correlation_id


async def test_ping_vendor_service_returns_parsed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"service": "vendor", "status": "ok"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        result = await ping_vendor_service("http://vendor-test", client=client)

    assert result == VendorPingResponse(service="vendor", status="ok")


async def test_ping_vendor_service_sends_ambient_correlation_id_header():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-correlation-id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={"service": "vendor", "status": "ok"})

    transport = httpx.MockTransport(handler)
    bind_correlation_id("corr-unit-test-1")
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await ping_vendor_service("http://vendor-test", client=client)

    assert captured["x-correlation-id"] == "corr-unit-test-1"


async def test_ping_vendor_service_explicit_correlation_id_overrides_ambient():
    captured: dict[str, str | None] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["x-correlation-id"] = request.headers.get("x-correlation-id")
        return httpx.Response(200, json={"service": "vendor", "status": "ok"})

    transport = httpx.MockTransport(handler)
    bind_correlation_id("corr-ambient")
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await ping_vendor_service("http://vendor-test", correlation_id="corr-explicit", client=client)

    assert captured["x-correlation-id"] == "corr-explicit"


async def test_ping_vendor_service_raises_typed_error_on_non_200():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, json={"error": "unavailable"})

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await ping_vendor_service("http://vendor-test", client=client)


async def test_ping_vendor_service_raises_typed_error_on_malformed_response():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not json")

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await ping_vendor_service("http://vendor-test", client=client)


async def test_ping_vendor_service_raises_typed_error_on_network_failure():
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("boom", request=request)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        with pytest.raises(VendorApiError):
            await ping_vendor_service("http://vendor-test", client=client)
```

Save as `tests/unit/test_vendor_api_contract.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_vendor_api_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.contracts.vendor_api'`.

- [ ] **Step 3: Write `packages/contracts/vendor_api.py`**

```python
"""The real, versioned network API contract between apps/api_tender and
apps/api_vendor (ADR-0006) -- packages/contracts' first real module. This
is deliberately a real httpx-based HTTP client, not an in-process function
call: it has real timeout/network-failure handling, because the two sides
are now separate deployable processes, not packages sharing one process.

Forwards the caller's ambient correlation id (packages/platform/
correlation.py's ContextVar, set by CorrelationIdMiddleware for the
current inbound request) as the X-Correlation-Id header -- the receiving
service's own CorrelationIdMiddleware instance already reads that header
on the way in (confirmed by reading its source; no changes needed there),
so correlation ids thread across the service boundary the same way they
already thread API -> worker -> outbox within one process (NFR-OBS-01)."""

from __future__ import annotations

import httpx
from pydantic import BaseModel, ValidationError

from packages.platform.correlation import CORRELATION_ID_HEADER, get_correlation_id_or_none


class VendorPingResponse(BaseModel):
    service: str
    status: str


class VendorApiError(Exception):
    """Any failure calling the vendor service: unreachable, non-200, or a
    response that doesn't match the contract -- always this one typed
    error, never a bare httpx/pydantic exception leaking to the caller."""


async def ping_vendor_service(
    base_url: str,
    *,
    correlation_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> VendorPingResponse:
    resolved_correlation_id = correlation_id or get_correlation_id_or_none()
    headers = {CORRELATION_ID_HEADER: resolved_correlation_id} if resolved_correlation_id else {}

    owns_client = client is None
    http_client = client or httpx.AsyncClient()
    try:
        response = await http_client.get(f"{base_url}/internal/ping", headers=headers, timeout=10.0)
    except httpx.HTTPError as exc:
        raise VendorApiError(f"vendor service unreachable: {exc}") from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code != 200:
        raise VendorApiError(f"vendor service returned status {response.status_code}: {response.text}")

    try:
        payload = response.json()
    except ValueError as exc:
        raise VendorApiError(f"vendor service returned non-JSON response: {exc}") from exc

    try:
        return VendorPingResponse.model_validate(payload)
    except ValidationError as exc:
        raise VendorApiError(f"vendor service response does not match contract: {exc}") from exc
```

Save as `packages/contracts/vendor_api.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_vendor_api_contract.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/contracts/vendor_api.py tests/unit/test_vendor_api_contract.py
git commit -m "feat(contracts): real network API contract for vendor ping (ADR-0006, task 4/6)"
```

---

## Task 5: End-to-end contract proof — real `apps/api_vendor` + real client

**Files:**
- Test: `tests/contract/test_tender_vendor_contract.py`

**Interfaces:**
- Consumes: `apps.api_vendor.main.create_app` (Task 2), `packages.contracts.vendor_api.
  ping_vendor_service`/`VendorPingResponse` (Task 4).
- Produces: nothing new — this is the first real test in `tests/contract/`, proving Tasks 2-4 actually
  interoperate over a real (ASGI-transport-backed) HTTP round trip, not just against a mock.

- [ ] **Step 1: Write the test** (no red/green cycle needed here — this composes already-built,
  already-tested pieces; it is a real-data integration proof, the same shape as this repo's other
  cross-component proofs, e.g. `tests/integration/test_object_region_intersection_store.py`)

```python
"""tests/contract's first real test (tests/README.md: "OpenAPI/schema
contracts, synthetic vs real adapter parity"): proves packages/contracts'
vendor_api client and the real apps/api_vendor app actually speak the same
schema over a real HTTP-shaped round trip (ADR-0006), not just against a
mock transport (see tests/unit/test_vendor_api_contract.py for the mocked
unit tests). Uses httpx.ASGITransport -- no real TCP port, but a real
ASGI/HTTP request-response cycle including headers and middleware."""

from __future__ import annotations

import httpx

from apps.api_vendor.main import create_app as create_vendor_app
from packages.contracts.vendor_api import VendorPingResponse, ping_vendor_service
from packages.platform.correlation import bind_correlation_id
from packages.platform.settings import Settings


async def test_ping_vendor_service_round_trip_against_the_real_vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=8)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine
    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)

    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        result = await ping_vendor_service("http://vendor-test", client=client)

    assert result == VendorPingResponse(service="vendor", status="ok")


async def test_ping_vendor_service_ambient_correlation_id_reaches_the_real_vendor_app_middleware(engine, _database_url):
    # Proves cross-service propagation end to end: the real
    # CorrelationIdMiddleware running inside the real vendor app echoes
    # back whatever correlation id it received on the response -- if the
    # client's ambient id didn't reach it, this would echo a freshly
    # minted id instead.
    settings = Settings(database_url=_database_url, expected_schema_version=8)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine
    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)

    bind_correlation_id("corr-cross-service-e2e-1")
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await ping_vendor_service("http://vendor-test", client=client)
        # A second, direct call confirms what the middleware actually saw
        # and echoed for a request carrying that same ambient id.
        response = await client.get("/internal/ping", headers={"X-Correlation-Id": "corr-cross-service-e2e-1"})

    assert response.headers["X-Correlation-Id"] == "corr-cross-service-e2e-1"
```

Save as `tests/contract/test_tender_vendor_contract.py`.

- [ ] **Step 2: Run it**

Run: `python -m pytest tests/contract/test_tender_vendor_contract.py -v`
Expected: both PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/contract/test_tender_vendor_contract.py
git commit -m "test(contract): real apps/api_vendor + vendor_api client round-trip proof (ADR-0006, task 5/6)"
```

---

## Task 6: Docs, open questions, full gate, branch + PR + CI + merge

**Files:**
- Modify: `CLAUDE.md`
- Modify: `AGENTS.md`
- Modify: `docs/operations/container-conventions.md`
- Modify: `docs/adr/0006-tender-vendor-service-separation.md`
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

- [ ] **Step 1: Update `CLAUDE.md`**

In the `## Commands` section, replace:

```
# Run the API (dev)
uvicorn apps.api.main:app --reload
```

with:

```
# Run the API (dev) -- two separate services (ADR-0006)
uvicorn apps.api_tender.main:app --reload --port 8001
uvicorn apps.api_vendor.main:app --reload --port 8002
```

In the `## Architecture` section's repo-map code block, replace the `apps/api` line:

```
apps/api              FastAPI, contract-first (OpenAPI is the source of truth), request/response only
```

with:

```
apps/api_tender       FastAPI (Tender service), contract-first, request/response only
apps/api_vendor       FastAPI (Vendor service) -- ADR-0006: separate deployable process from
                      api_tender, communicating via packages/contracts, not a shared process
```

- [ ] **Step 2: Update `AGENTS.md` §5 repository map**

Read the file first. In the `apps/` block, replace:

```
    api                   FastAPI — request/response only, no long external calls in-request
```

with:

```
    api_tender            FastAPI (Tender service) — request/response only, no long external calls
    api_vendor            FastAPI (Vendor service, ADR-0006) — separate deployable process from
                          api_tender, real API contract via packages/contracts, not a shared process
```

- [ ] **Step 3: Update `docs/operations/container-conventions.md`**

Read the file first. Change the line listing images from `apps/api`, `apps/worker` to
`apps/api_tender`, `apps/api_vendor`, `apps/worker` (three images now, not two).

- [ ] **Step 4: Add a footnote to ADR-0006**

Append to `docs/adr/0006-tender-vendor-service-separation.md`, right after its `## Decision` section's
first bullet (the one naming `apps/api-tender`/`apps/api-vendor`):

```markdown
> **Naming note (2026-08-05, at implementation time):** the actual directories/import paths are
> `apps/api_tender` and `apps/api_vendor` (underscores) — Python package names cannot contain hyphens.
> The hyphenated form above refers to the deployable service name (process/image/deploy target), not
> the Python package path.
```

- [ ] **Step 5: Run the full gate**

Run:
```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```
Expected: 0 failures, 0 issues, `PASS: v1 untouched`.

- [ ] **Step 6: WORKLOG entry**

Append to `docs/reports/WORKLOG.md` (match existing entries' tone: `**Сделано:**`, `**Вывод полного
прогона (Fast+Full gate):**`, `**Дальше:**`, `**Блокеры:**`). Content to include:

- This closes the "next task" ADR-0006 itself named (`docs/reports/DEVELOPMENT-PAUSED-2026-08-05.md`,
  §7): `apps/api` is now `apps/api_tender` + `apps/api_vendor`, two independent FastAPI processes.
- `packages/contracts` has its first real code: `vendor_api.py`, a real `httpx`-based network client
  (`ping_vendor_service`/`VendorPingResponse`/`VendorApiError`) proven both against a mock transport
  (`tests/unit/test_vendor_api_contract.py`, 6 tests) and against the real `apps/api_vendor` app over
  an ASGI-transport-backed HTTP round trip, including real cross-service correlation-id propagation
  (`tests/contract/test_tender_vendor_contract.py` — the first real test in that previously-empty
  directory).
- What was deliberately not built: `/internal/ping` is unauthenticated (real service-to-service auth
  deferred to `D-IDP`/`D-HOST`, recorded in `docs/decisions/OPEN-QUESTIONS.md`); database/CI/CD/hosting
  topology unchanged (both apps still point at one shared PostgreSQL instance); `apps/worker` untouched.
- Files: `apps/api_tender/*` (renamed from `apps/api/*`), `apps/api_vendor/*` (new),
  `packages/contracts/vendor_api.py` (new), plus the test files listed in Tasks 1-5.
- Paste the actual `pytest`/`ruff`/`mypy`/`check_v1_untouched.py` output from Step 5 — do not fabricate
  pass counts.

- [ ] **Step 7: Open Questions entry**

Append to `docs/decisions/OPEN-QUESTIONS.md` (same format: `**Context:**`, `**Deviation/assumption:**`,
`**Consequence that must not be silently dropped:**`, `**Owner follow-up needed:**`). Content:

- Context: ADR-0006's split is now implemented — `apps/api_tender`/`apps/api_vendor` are real, separate
  FastAPI processes with a real network contract (`packages/contracts/vendor_api.py`) between them.
- Deviation/assumption: `GET /internal/ping` (the one real vendor endpoint proving the contract
  mechanism) is unauthenticated — no `D-IDP`-backed service-to-service auth exists yet, and building one
  speculatively for a proof endpoint with no real data would be scope creep beyond ADR-0006's own
  explicitly-deferred items.
- Consequence: any *future* `/internal/*` or vendor-domain endpoint that carries real data must not
  copy this endpoint's unauthenticated pattern — it exists only because this endpoint returns a static,
  non-sensitive value. Also: `apps/api_tender` and `apps/api_vendor` currently share one PostgreSQL
  instance with only application-layer table separation (unchanged from ADR-0006's own explicit
  non-decision on database topology) — still open, tied to `TBD-05`/`D-HOST`.
- Owner follow-up needed: No, not blocking. Real service-to-service auth and database-per-service
  topology remain future work once `D-IDP`/`D-HOST`/`TBD-05` resolve.

- [ ] **Step 8: Commit the docs**

```bash
git add CLAUDE.md AGENTS.md docs/operations/container-conventions.md docs/adr/0006-tender-vendor-service-separation.md docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(arch): apps/api_tender + apps/api_vendor split done, record open items (ADR-0006, task 6/6)"
```

- [ ] **Step 9: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b apps-api-tender-vendor-split
git push -u origin apps-api-tender-vendor-split
gh pr create --base master --head apps-api-tender-vendor-split \
  --title "feat(api): split apps/api into apps/api_tender + apps/api_vendor (ADR-0006)" \
  --body "Implements ADR-0006: apps/api renamed to apps/api_tender; new apps/api_vendor skeleton with GET /internal/ping; packages/contracts gets its first real module (vendor_api.py, a real httpx-based network client), proven both against a mock transport and against the real apps/api_vendor app over an ASGI-transport-backed HTTP round trip including cross-service correlation-id propagation. See docs/decisions/OPEN-QUESTIONS.md and docs/adr/0006-tender-vendor-service-separation.md for full context and explicitly-deferred items (auth, DB topology)."
```

Wait for both `Fast gate` and `Full gate` to report `pass` via `gh pr checks <number>` (poll every couple
of minutes — do not block synchronously; `live-fetch` job is expected to show `fail`, that is normal
and does not block merge, see `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-05, the `etender.gov.az`
entry). Once both required checks pass:

```bash
gh pr merge <number> --rebase --delete-branch
git fetch --prune
git checkout master
git reset --hard origin/master
```

(If there are unrelated uncommitted changes in the working tree at this point, e.g. an in-progress
edit to `CLAUDE.md` from a different task, `git stash push -u` before the reset and `git stash pop`
after, to avoid losing them — same pattern used earlier this session.)

---

## Self-review notes

- **Spec coverage:** ADR-0006's concrete decisions (two FastAPI processes; `packages/contracts`
  promoted to a real network contract; `platform` stays shared; `apps/worker` untouched; DB/CI/CD
  topology left open) each map to a task above. The ADR's naming looseness (`apps/api-tender` prose vs.
  the real `apps/api_tender` Python package path) is called out and fixed via Task 6 Step 4's ADR
  footnote.
- **No placeholders:** every step has real, complete code — no "add appropriate error handling" left
  unstated; `VendorApiError`'s three raise sites (unreachable, non-200, malformed) are each written out
  and each has its own unit test.
- **Type consistency:** `VendorPingResponse`/`VendorApiError`/`ping_vendor_service` (Task 4) are used
  with identical names/signatures in Task 5's contract test. `apps.api_vendor.main.create_app` (Task 2)
  is reused unchanged by Task 3 (adds a router to the same file) and Task 5 (imports it directly).
