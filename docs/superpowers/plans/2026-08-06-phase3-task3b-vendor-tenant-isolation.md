# Phase 3, Task 3.B — Vendor tenant isolation (FR-VND-09) Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close `FR-VND-09` ("Tenant isolation проверяется тестами на уровнях route, service и
database", P0, PRD §5.5/§9.2) for the vendor domain: prove that one vendor's offers can never be
returned by a query scoped to another vendor, with a real test at each of the three named levels.

**Architecture:** Today `packages/vendor`'s schema has no per-vendor scoping concept beyond the
`vendor_offers.vendor_id` foreign key, and `apps/api_vendor` has no real data-bearing route at all
(only the deliberately unauthenticated `/internal/ping` proof endpoint). This task introduces the
minimum real mechanism needed to test all three levels honestly:
- **Database level:** a raw-SQL test proves that filtering `vendor_offers` by `vendor_id` never
  returns another vendor's rows, even when both vendors' rows physically coexist in the same table.
- **Service level:** a new `packages/vendor/vendor_store.py` function, `list_offers_by_vendor()`,
  is the only way the service layer exposes a single vendor's offers — tested by calling it directly
  (no HTTP) with two vendors seeded, proving the Python-level API itself cannot leak across vendors.
- **Route level:** a new, real vendor-facing route, `GET /vendors/me/offers`, is added to
  `apps/api_vendor`. Each vendor gets a server-issued API key (`vendors.api_key`, a new column) at
  creation. The route resolves the calling vendor's identity **only** from that key (never from a
  client-supplied `vendor_id` — there is no such parameter anywhere in the route), so there is no
  input a caller could manipulate to reach another vendor's data. Deny-by-default (`INV-08`, same
  discipline as `apps/api_tender/deps.py::get_current_identity`): a missing or unknown key is
  unauthenticated (401), never a default identity.

This is a Phase-3, sandbox-only credential mechanism — **not** the pilot's internal identity
provider decision (`D-IDP`, Entra/OIDC for human users, still open) and does not resolve it; real
vendor onboarding (Phase 7, `PLAN-MISSION-7.md`) may replace this mechanism entirely once that gate
opens. Recorded as an explicit implementation choice in Task 7, not silently assumed permanent.

**Out of scope, recorded not silently skipped:** Postgres Row-Level Security (a defense-in-depth
mechanism that would enforce vendor scoping even against a hypothetical future query that forgets a
`WHERE vendor_id = ...` clause) is not built here — no other table in this codebase uses RLS yet,
and the PRD's own wording only asks for tests "at the route, service, and database levels", not for
a specific enforcement mechanism at each level. If a future task needs defense-in-depth beyond
correct application-level scoping, that is new, separately-scoped work.

**Tech Stack:** Python 3.12 stdlib `secrets` module (API key generation) — no new dependency.

## Global Constraints

- `FR-VND-09` (PRD §5.5 line 323, exit criterion for Phase 3 per PRD §10.1 — confirmed the PRD's own
  roadmap table lists `FR-VND-09` under Phase 3, not Phase 7, resolving the doc-drift between
  `PLAN-MISSION-3.md`/`PLAN-MISSION-7.md` and the PRD in favor of the PRD, per `AGENTS.md` §1's
  conflict rule and the owner's explicit direction this session).
- Every vendor row gets exactly one server-generated `api_key` — never client-supplied, never
  omitted (same "no silent fallback" discipline as `data_realm`/`watermark`, `INV-11`).
- The route never accepts a vendor id from the caller (path, query, or body) for reading "my own"
  offers — the only vendor-scoping input is the resolved identity. This is what makes the isolation
  structural, not just "remembered to add a WHERE clause".
- This migration (`0010`) bumps the real schema ledger version from 9 to 10 — every hardcoded `9` in
  existing tests/settings that refers to *the current* schema version (not a deliberate mismatch
  value like `99`) must be bumped to `10` in the same change (same pattern as the two prior
  `6→7`/`8→9` follow-ups recorded in `docs/reports/WORKLOG.md`).
- Every commit lands via a feature branch + PR + green CI (Fast + Full gate).
- Every requirement ID used must trace to `TENDER_INTELLIGENCE_SPEC.md` §6.1 / PRD §5.5, `FR-VND-09`,
  `FR-VND-05`, `FR-VND-06`, `INV-08`, `INV-11`, `NFR-PRV-04` — already-existing IDs. Do not invent a
  new one.

---

## Task 1: Migration `0010` — `vendors.api_key`, and the schema-version ripple

**Files:**
- Create: `migrations/0010_vendor_api_key.sql`
- Modify: `packages/platform/settings.py:24`
- Modify: `tests/integration/test_migrations_runner.py:26,27,35,56,126`
- Modify: `tests/integration/test_api_tender_health.py:14,33` (NOT line 37 — that `99` is a
  deliberate mismatch value, leave it)
- Modify: `tests/integration/test_api_vendor_health.py:15,34`
- Modify: `tests/contract/test_tender_vendor_contract.py:20,37`
- Modify: `tests/integration/test_vendor_sandbox_migration.py:16,25,40` (add `api_key` to the three
  raw `INSERT INTO vendors` statements — they will fail against the new `NOT NULL` column otherwise)

**Interfaces:**
- Produces: `vendors.api_key TEXT NOT NULL UNIQUE` column. Real schema ledger version `10`.

- [ ] **Step 1: Write the migration**

```sql
-- Vendor tenant isolation (FR-VND-09, PRD §5.5/§9.2, INV-08): each vendor
-- gets a server-issued API key, unique, never client-supplied, never
-- omitted. This is the identity apps/api_vendor's new /vendors/me/offers
-- route resolves the caller from -- there is no other per-vendor
-- credential concept in this schema yet. NOT NULL with no default is
-- safe here: this table has been sandbox-only synthetic data since
-- migration 0009 landed, no real vendor onboarding gate has opened
-- (ADR-0004), so there is no production data an unconditional NOT NULL
-- addition could break.

ALTER TABLE vendors ADD COLUMN api_key TEXT NOT NULL UNIQUE;
```

Save as `migrations/0010_vendor_api_key.sql`.

- [ ] **Step 2: Bump every hardcoded "current schema version" reference from 9 to 10**

`packages/platform/settings.py:24` — change the `EXPECTED_SCHEMA_VERSION` env-var default:

```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "10")))
```

`tests/integration/test_migrations_runner.py`:
- Line 26: `assert versions == {1, 2, 3, 4, 5, 6, 7, 8, 9}` → `assert versions == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}`
- Line 27: `assert await runner.current_version() == 9` → `== 10`
- Line 35: `assert await runner.current_version() == 9` → `== 10`
- Line 56: `assert {m.version for m in applied} == {2, 3, 4, 5, 6, 7, 8, 9}` → add `, 10`
- Line 126: `assert version == 9` → `== 10` (and its `expected_version=9` call argument on the line
  above it, line 125, → `expected_version=10`)

`tests/integration/test_api_tender_health.py`:
- Line 14: `expected_schema_version=9` → `expected_schema_version=10`
- Line 33: `assert body["schema_version"] == 9` → `== 10`
- Line 37 (`expected_schema_version=99`): leave unchanged — it is a deliberate mismatch value for
  `test_readiness_fails_on_schema_mismatch`, not tied to the real current version.

`tests/integration/test_api_vendor_health.py`:
- Line 15: `expected_schema_version=9` → `expected_schema_version=10`
- Line 34: `assert body["schema_version"] == 9` → `== 10`

`tests/contract/test_tender_vendor_contract.py`:
- Line 20: `expected_schema_version=9` → `expected_schema_version=10`
- Line 37: `expected_schema_version=9` → `expected_schema_version=10`

- [ ] **Step 3: Fix the raw-SQL vendor inserts in `test_vendor_sandbox_migration.py`**

Read the file first (already read above — three raw `INSERT INTO vendors` statements at lines 16-19,
25-28, and 40-43, none of which list `api_key`). Add an `api_key` column and value to each:

Line 16-19 becomes:

```python
        await conn.execute(
            text(
                "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Test Vendor', 'synthetic', 1, 'test-key-1')"
            )
        )
```

Line 25-28 becomes:

```python
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'REAL', 'Bad Vendor', 'synthetic', 1, 'test-key-2')"
                )
```

Line 40-43 becomes:

```python
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Test Vendor 2', 'synthetic', 2, 'test-key-3') RETURNING id"
                )
```

- [ ] **Step 4: Run the affected tests to verify they pass**

Run: `python -m pytest tests/integration/test_migrations_runner.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py tests/contract/test_tender_vendor_contract.py tests/integration/test_vendor_sandbox_migration.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/0010_vendor_api_key.sql packages/platform/settings.py tests/integration/test_migrations_runner.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py tests/contract/test_tender_vendor_contract.py tests/integration/test_vendor_sandbox_migration.py
git commit -m "feat(vendor): add vendors.api_key column (FR-VND-09 prep), bump schema version 9->10"
```

---

## Task 2: `vendor_store.py` — issue API keys, resolve identity, scope offers by vendor

**Files:**
- Modify: `packages/vendor/vendor_store.py`
- Modify: `tests/integration/test_vendor_store.py:19-22,46-50` (call-site fix for `store_vendor`'s
  changed return type)

**Interfaces:**
- Produces:
  - `store_vendor(conn: AsyncConnection, vendor: Vendor) -> tuple[int, str]` (was `-> int`; now
    returns `(vendor_id, api_key)` — the key is generated here, server-side, never supplied by the
    caller).
  - `get_vendor_id_by_api_key(conn: AsyncConnection, *, api_key: str) -> int | None` (deny-by-default:
    unknown key → `None`, same discipline as `packages/platform/rbac/store.py::resolve_identity`).
  - `list_offers_by_vendor(conn: AsyncConnection, *, vendor_id: int) -> list[dict[str, Any]]`.
- Consumes: `Vendor`/`Offer` (existing, unchanged — `api_key` is a store-assigned credential, not a
  domain-model field, so `SyntheticProvider`/`CsvProvider` need no changes).

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_vendor_store_api_key.py`... actually this module needs a real `AsyncConnection`,
so it belongs in integration, not unit. Add these three tests to
`tests/integration/test_vendor_store.py` (append to the existing file, keep its existing two tests
unchanged except for the call-site fix in Step 4 below):

```python
from packages.vendor.vendor_store import get_vendor_id_by_api_key, list_offers_by_vendor


async def test_store_vendor_issues_a_unique_server_generated_api_key(engine):
    vendor_a = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="A", provider_type="synthetic", seed=1)
    vendor_b = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="B", provider_type="synthetic", seed=2)

    async with engine.begin() as conn:
        _id_a, key_a = await store_vendor(conn, vendor_a)
        _id_b, key_b = await store_vendor(conn, vendor_b)

    assert key_a != key_b
    assert key_a and key_b  # never empty


async def test_get_vendor_id_by_api_key_resolves_the_right_vendor(engine):
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="C", provider_type="synthetic", seed=3)

    async with engine.begin() as conn:
        vendor_id, api_key = await store_vendor(conn, vendor)
        resolved = await get_vendor_id_by_api_key(conn, api_key=api_key)

    assert resolved == vendor_id


async def test_get_vendor_id_by_api_key_denies_an_unknown_key(engine):
    async with engine.begin() as conn:
        resolved = await get_vendor_id_by_api_key(conn, api_key="not-a-real-key")

    assert resolved is None
```

Add `from packages.vendor.vendor_model import Vendor` to the file's imports if not already present
(check the existing imports first — the file currently only imports `SyntheticProvider` and the
store functions, not `Vendor` directly).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_vendor_store.py -v`
Expected: FAIL — `ImportError: cannot import name 'get_vendor_id_by_api_key'` (and the existing two
tests will also start failing once Step 4 changes their call sites, but do Step 4 together with this
so the file is internally consistent — see note in Step 4).

- [ ] **Step 3: Implement the store changes**

Read `packages/vendor/vendor_store.py` first (already read above). Add `import secrets` to the
imports. Change `store_vendor`:

```python
async def store_vendor(conn: AsyncConnection, vendor: Vendor) -> tuple[int, str]:
    api_key = secrets.token_hex(32)
    vendor_id = (
        await conn.execute(
            text(
                """
                INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key)
                VALUES (:data_realm, :watermark, :name, :provider_type, :seed, :api_key)
                RETURNING id
                """
            ),
            {
                "data_realm": vendor.data_realm,
                "watermark": vendor.watermark,
                "name": vendor.name,
                "provider_type": vendor.provider_type,
                "seed": vendor.seed,
                "api_key": api_key,
            },
        )
    ).scalar_one()
    return vendor_id, api_key
```

Add two new functions at the end of the file:

```python
async def get_vendor_id_by_api_key(conn: AsyncConnection, *, api_key: str) -> int | None:
    row = (await conn.execute(text("SELECT id FROM vendors WHERE api_key = :api_key"), {"api_key": api_key})).first()
    return row[0] if row is not None else None


async def list_offers_by_vendor(conn: AsyncConnection, *, vendor_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, vendor_id, data_realm, watermark, material, price, currency, vat_rate,
                           uom, uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                           evidence_source, observed_at, adverse_case
                    FROM vendor_offers WHERE vendor_id = :vendor_id ORDER BY id
                    """
                ),
                {"vendor_id": vendor_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

- [ ] **Step 4: Fix the existing tests' call sites for `store_vendor`'s new return type**

In `tests/integration/test_vendor_store.py`, both existing tests currently do
`vendor_ids[vendor.name] = await store_vendor(conn, vendor)`. `store_vendor` now returns a tuple.
Change both occurrences (line 20 and line 48, in the two pre-existing test functions) to:

```python
            vendor_ids[vendor.name], _ = await store_vendor(conn, vendor)
```

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_vendor_store.py -v`
Expected: all 5 PASS (2 existing + 3 new).

- [ ] **Step 6: Commit**

```bash
git add packages/vendor/vendor_store.py tests/integration/test_vendor_store.py
git commit -m "feat(vendor): server-issued API keys, get_vendor_id_by_api_key, list_offers_by_vendor (FR-VND-09)"
```

---

## Task 3: Database-level isolation test (raw SQL)

**Files:**
- Create: `tests/integration/test_vendor_tenant_isolation_db.py`

**Interfaces:**
- Consumes: nothing from `packages/vendor` — this test deliberately uses raw SQL only, to prove
  isolation holds at the database layer itself, independent of any Python wrapper.

- [ ] **Step 1: Write the test**

```python
"""Database-level proof for FR-VND-09 (PRD §5.5/§9.2): filtering
vendor_offers by vendor_id at the SQL layer itself -- not through any
packages/vendor Python function -- never returns another vendor's rows,
even when both vendors' offers physically coexist in the same table with
otherwise-identical field values (same material/price/currency), so the
only thing that could distinguish them is vendor_id itself."""

from __future__ import annotations

from sqlalchemy import text


async def test_raw_sql_scoped_by_vendor_id_never_returns_another_vendors_offers(engine):
    async with engine.begin() as conn:
        vendor_a_id = (
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Tenant A', 'synthetic', 1, 'db-test-key-a') "
                    "RETURNING id"
                )
            )
        ).scalar_one()
        vendor_b_id = (
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed, api_key) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Tenant B', 'synthetic', 2, 'db-test-key-b') "
                    "RETURNING id"
                )
            )
        ).scalar_one()

        # Identical fields on both offers except vendor_id -- vendor_id is
        # the *only* thing a scoped query could rely on.
        for vendor_id in (vendor_a_id, vendor_b_id):
            await conn.execute(
                text(
                    "INSERT INTO vendor_offers "
                    "(vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom, "
                    " uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until, "
                    " evidence_source, observed_at) "
                    "VALUES (:vendor_id, 'vendor-sandbox', 'SYNTHETIC', 'rebar-16mm', 870.5, 'AZN', 18.0, 'ton', "
                    " 1.0, 5.0, 150.0, 90.0, now(), now(), 'db-isolation-test', now())"
                ),
                {"vendor_id": vendor_id},
            )

        rows_for_a = (
            (
                await conn.execute(
                    text("SELECT vendor_id FROM vendor_offers WHERE vendor_id = :vendor_id"),
                    {"vendor_id": vendor_a_id},
                )
            )
            .mappings()
            .all()
        )

    assert len(rows_for_a) == 1
    assert rows_for_a[0]["vendor_id"] == vendor_a_id
    assert rows_for_a[0]["vendor_id"] != vendor_b_id
```

- [ ] **Step 2: Run test to verify it fails first, honestly**

Run: `python -m pytest tests/integration/test_vendor_tenant_isolation_db.py -v`
Expected: this should already PASS against the current schema/data (the `vendor_id` FK column has
existed since migration `0009` — this test is a *proof*, not a bug fix). If it fails, the failure
means the `api_key` column added in Task 1 broke the raw INSERT (check the column list matches the
real table); fix the INSERT before proceeding, don't weaken the assertion.

- [ ] **Step 3: Confirm it passes**

Run: `python -m pytest tests/integration/test_vendor_tenant_isolation_db.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_vendor_tenant_isolation_db.py
git commit -m "test(vendor): database-level tenant isolation proof (FR-VND-09)"
```

---

## Task 4: Service-level isolation test (`list_offers_by_vendor`)

**Files:**
- Create: `tests/integration/test_vendor_tenant_isolation_service.py`

**Interfaces:**
- Consumes: `store_vendor`, `store_offer`, `list_offers_by_vendor` (Task 2), `Vendor`/`Offer`
  (existing).

- [ ] **Step 1: Write the test**

```python
"""Service-level proof for FR-VND-09 (PRD §5.5/§9.2): packages/vendor's
own list_offers_by_vendor() function -- the service layer's public API
for reading one vendor's offers -- never returns another vendor's rows,
called directly (no HTTP, no raw SQL), with two vendors' real synthetic
generator output stored side by side."""

from __future__ import annotations

from packages.vendor.synthetic_provider import SyntheticProvider
from packages.vendor.vendor_store import list_offers_by_vendor, store_offer, store_vendor

AS_OF = "2026-08-06T00:00:00+00:00"


async def test_list_offers_by_vendor_never_returns_another_vendors_offers(engine):
    vendors_a, offers_a = SyntheticProvider(seed=101).generate(as_of=AS_OF)
    vendors_b, offers_b = SyntheticProvider(seed=102).generate(as_of=AS_OF)

    async with engine.begin() as conn:
        ids_a: dict[str, int] = {}
        for vendor in vendors_a:
            vendor_id, _api_key = await store_vendor(conn, vendor)
            ids_a[vendor.name] = vendor_id
        for offer in offers_a:
            await store_offer(conn, ids_a[offer.vendor_name], offer)

        ids_b: dict[str, int] = {}
        for vendor in vendors_b:
            vendor_id, _api_key = await store_vendor(conn, vendor)
            ids_b[vendor.name] = vendor_id
        for offer in offers_b:
            await store_offer(conn, ids_b[offer.vendor_name], offer)

        # Ask for one specific vendor from seed=101's batch.
        one_vendor_id = next(iter(ids_a.values()))
        rows = await list_offers_by_vendor(conn, vendor_id=one_vendor_id)

    assert len(rows) > 0
    assert all(row["vendor_id"] == one_vendor_id for row in rows)
    assert all(row["vendor_id"] not in ids_b.values() for row in rows)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_vendor_tenant_isolation_service.py -v`
Expected: PASS immediately if Task 2 is already committed (this is a proof of already-implemented
behavior, same honest framing as Task 3). If `list_offers_by_vendor` is missing, it fails with
`ImportError` — confirm Task 2 landed first.

- [ ] **Step 3: Confirm it passes**

Run: `python -m pytest tests/integration/test_vendor_tenant_isolation_service.py -v`
Expected: PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_vendor_tenant_isolation_service.py
git commit -m "test(vendor): service-level tenant isolation proof (FR-VND-09)"
```

---

## Task 5: Route-level mechanism — vendor identity + `GET /vendors/me/offers`

**Files:**
- Create: `apps/api_vendor/deps.py`
- Create: `apps/api_vendor/routers/offers.py`
- Modify: `apps/api_vendor/main.py:19,42` (import and register the new router)

**Interfaces:**
- Produces:
  - `apps/api_vendor/deps.py::get_connection(request: Request) -> AsyncIterator[AsyncConnection]`
    (identical shape to `apps/api_tender/deps.py::get_connection`).
  - `apps/api_vendor/deps.py::get_current_vendor_id(request: Request, x_vendor_api_key: str | None = Header(default=None)) -> int`
    — raises `ApiError(401, ...)` on missing/unknown key.
  - `apps/api_vendor/routers/offers.py::router` (APIRouter, `prefix="/vendors"`), route
    `GET /vendors/me/offers`.
- Consumes: `get_vendor_id_by_api_key`, `list_offers_by_vendor` (Task 2).

- [ ] **Step 1: Write `apps/api_vendor/deps.py`**

```python
"""Vendor-side identity resolution for FR-VND-09 (route-level tenant
isolation). This is a Phase-3, sandbox-only credential mechanism (a
server-issued API key per synthetic vendor) -- deliberately NOT the
pilot's internal identity provider decision (D-IDP, Entra/OIDC for human
users, still open) and does not resolve it. Real vendor onboarding
(Phase 7, docs/reports/PLAN-MISSION-7.md) may replace this mechanism
entirely once that gate opens -- recorded in
docs/decisions/OPEN-QUESTIONS.md, not assumed permanent."""

from __future__ import annotations

from collections.abc import AsyncIterator

from fastapi import Header, Request
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.errors import ApiError
from packages.vendor.vendor_store import get_vendor_id_by_api_key


async def get_connection(request: Request) -> AsyncIterator[AsyncConnection]:
    engine = request.app.state.engine
    async with engine.begin() as conn:
        yield conn


async def get_current_vendor_id(
    request: Request,
    x_vendor_api_key: str | None = Header(default=None),
) -> int:
    """Deny-by-default (INV-08, same discipline as
    apps/api_tender/deps.py::get_current_identity): a missing header or an
    unknown api_key are both unauthenticated, never a default vendor
    identity."""
    if x_vendor_api_key is None:
        raise ApiError(status_code=401, code="unauthenticated", message="X-Vendor-Api-Key header required")

    engine = request.app.state.engine
    async with engine.connect() as conn:
        vendor_id = await get_vendor_id_by_api_key(conn, api_key=x_vendor_api_key)
    if vendor_id is None:
        raise ApiError(status_code=401, code="unauthenticated", message="unknown api key")
    return vendor_id
```

- [ ] **Step 2: Write `apps/api_vendor/routers/offers.py`**

```python
"""Vendor-facing offers route (FR-VND-09 route-level tenant isolation
proof): GET /vendors/me/offers returns ONLY the calling vendor's own
offers. The vendor_id comes exclusively from the resolved identity
(get_current_vendor_id) -- it is never a path/query/body parameter here,
so there is no vendor_id value a caller could supply to reach another
vendor's data."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.vendor.vendor_store import list_offers_by_vendor

from ..deps import get_connection, get_current_vendor_id

router = APIRouter(prefix="/vendors", tags=["vendors"])


class OfferResponse(BaseModel):
    id: int
    vendor_id: int
    data_realm: str
    watermark: str
    material: str
    price: float
    currency: str
    vat_rate: float
    uom: str
    uom_canonical_qty: float
    moq: float
    capacity: float
    inventory: float
    valid_from: datetime
    valid_until: datetime
    evidence_source: str
    observed_at: datetime
    adverse_case: str | None


class OfferListResponse(BaseModel):
    items: list[OfferResponse]


@router.get("/me/offers", response_model=OfferListResponse)
async def list_my_offers(
    conn: AsyncConnection = Depends(get_connection),
    vendor_id: int = Depends(get_current_vendor_id),
) -> OfferListResponse:
    rows = await list_offers_by_vendor(conn, vendor_id=vendor_id)
    return OfferListResponse(items=[OfferResponse(**row) for row in rows])
```

- [ ] **Step 3: Wire the router into `apps/api_vendor/main.py`**

Read the file first (already read above). Change line 19's import and line 42's registration:

```python
from .routers import health, internal, offers
```

```python
    app.include_router(health.router)
    app.include_router(internal.router)
    app.include_router(offers.router)
```

- [ ] **Step 4: Sanity-check the app still builds**

Run: `python -c "from apps.api_vendor.main import create_app; create_app()"`
Expected: no exception (this only proves the app/router wiring imports cleanly — the real behavior
is tested in Task 6).

- [ ] **Step 5: Run the full unit+mypy gate for this task's new files**

Run: `python -m mypy packages/vendor apps/api_vendor`
Expected: `Success: no issues found`.

- [ ] **Step 6: Commit**

```bash
git add apps/api_vendor/deps.py apps/api_vendor/routers/offers.py apps/api_vendor/main.py
git commit -m "feat(vendor): GET /vendors/me/offers, API-key vendor identity (FR-VND-09 route mechanism)"
```

---

## Task 6: Route-level isolation test (real HTTP, deny-by-default)

**Files:**
- Create: `tests/security/test_vendor_tenant_isolation_route.py`

**Interfaces:**
- Consumes: `create_app` (`apps/api_vendor/main.py`), `store_vendor`, `store_offer` (existing),
  `Vendor`/`Offer` (existing). Same `client` fixture pattern as
  `tests/integration/test_api_vendor_health.py`.

- [ ] **Step 1: Write the test**

```python
"""Route-level proof for FR-VND-09 (PRD §5.5/§9.2, INV-08): a real HTTP
request to GET /vendors/me/offers, authenticated with vendor A's own
API key, never returns vendor B's offers -- and a request with no key,
or an unknown key, is denied (401), never given a default identity."""

from __future__ import annotations

import httpx
import pytest_asyncio

from apps.api_vendor.main import create_app
from packages.platform.settings import Settings
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor

AS_OF = "2026-08-06T00:00:00+00:00"


@pytest_asyncio.fixture
async def client(engine, _database_url, migrated_asyncpg_dsn):
    settings = Settings(database_url=_database_url, expected_schema_version=10)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as c:
        yield c


def _offer(vendor_name: str, material: str) -> Offer:
    return Offer(
        vendor_name=vendor_name,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material=material,
        price=100.0,
        currency="AZN",
        vat_rate=18.0,
        uom="ton",
        uom_canonical_qty=1.0,
        moq=1.0,
        capacity=10.0,
        inventory=5.0,
        valid_from=AS_OF,
        valid_until="2026-12-31T00:00:00+00:00",
        evidence_source="route-isolation-test",
        observed_at=AS_OF,
        adverse_case=None,
    )


async def test_a_vendor_only_sees_its_own_offers(client, engine):
    vendor_a = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Route Tenant A", provider_type="synthetic", seed=201
    )
    vendor_b = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Route Tenant B", provider_type="synthetic", seed=202
    )

    async with engine.begin() as conn:
        vendor_a_id, key_a = await store_vendor(conn, vendor_a)
        vendor_b_id, _key_b = await store_vendor(conn, vendor_b)
        await store_offer(conn, vendor_a_id, _offer("Route Tenant A", "rebar-16mm"))
        await store_offer(conn, vendor_b_id, _offer("Route Tenant B", "cement-42.5"))

    response = await client.get("/vendors/me/offers", headers={"X-Vendor-Api-Key": key_a})

    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["vendor_id"] == vendor_a_id
    assert body["items"][0]["material"] == "rebar-16mm"
    assert all(item["vendor_id"] != vendor_b_id for item in body["items"])


async def test_missing_api_key_is_denied_not_defaulted(client):
    response = await client.get("/vendors/me/offers")
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"


async def test_unknown_api_key_is_denied_not_defaulted(client):
    response = await client.get("/vendors/me/offers", headers={"X-Vendor-Api-Key": "not-a-real-key"})
    assert response.status_code == 401
    assert response.json()["error"]["code"] == "unauthenticated"
```

- [ ] **Step 2: Run test to verify it fails first, honestly**

Run: `python -m pytest tests/security/test_vendor_tenant_isolation_route.py -v`
Expected: PASS if Task 5 landed correctly (proof of already-implemented behavior). If any test
fails, read the failure — do not adjust the assertions to match a bug; fix the route/deps code from
Task 5 instead.

- [ ] **Step 3: Confirm it passes**

Run: `python -m pytest tests/security/test_vendor_tenant_isolation_route.py -v`
Expected: all 3 PASS.

- [ ] **Step 4: Commit**

```bash
git add tests/security/test_vendor_tenant_isolation_route.py
git commit -m "test(vendor): route-level tenant isolation proof, deny-by-default (FR-VND-09)"
```

---

## Task 7: WORKLOG, Open Questions, full gate, branch + PR + CI + merge

**Files:**
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

- [ ] **Step 1: Run the full gate**

```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```

- [ ] **Step 2: WORKLOG entry**

State: `FR-VND-09` closed for Phase 3. Record the doc-drift finding and resolution (PRD §10.1 lists
`FR-VND-09` under Phase 3's exit criteria; `PLAN-MISSION-3.md`/`PLAN-MISSION-7.md` had scoped it to
Phase 7 only — owner directed building it now, PRD wins, per `AGENTS.md` §1's conflict-resolution
rule). Describe the mechanism: server-issued per-vendor API key (`vendors.api_key`, migration `0010`),
`GET /vendors/me/offers` (first real vendor-facing route beyond `/internal/ping`), three isolation
tests (`tests/integration/test_vendor_tenant_isolation_db.py`,
`tests/integration/test_vendor_tenant_isolation_service.py`,
`tests/security/test_vendor_tenant_isolation_route.py`). Note explicitly: this does NOT resolve
`D-IDP` (the pilot's internal human-user identity provider decision is untouched) and does NOT build
RLS/defense-in-depth beyond correct application-level scoping (recorded as deliberately out of scope
above). Paste real gate output.

- [ ] **Step 3: Open Questions entry**

Record: `FR-VND-09` satisfied for Phase 3 via a Phase-3-scoped, sandbox-only API-key mechanism — not
a resolution of `D-IDP`, and not a claim that this mechanism survives real vendor onboarding (Phase 7
may need a genuinely different identity flow per its own onboarding state machine, e.g. invitation
→ credential issuance, which does not exist yet). Also record the doc-drift correction itself: note
that `PLAN-MISSION-3.md` should eventually be corrected to list `FR-VND-09` under 3.B (not left
absent) so future sessions reading only the mission plan don't re-derive this conflict from scratch —
flag as a follow-up doc fix, don't silently leave the plan doc stale.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(vendor): record FR-VND-09 closure and PRD-vs-plan doc-drift resolution"
```

- [ ] **Step 5: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b phase3-task3b-vendor-tenant-isolation
git push -u origin phase3-task3b-vendor-tenant-isolation
gh pr create --base master --head phase3-task3b-vendor-tenant-isolation \
  --title "feat(vendor): tenant isolation route/service/database tests (FR-VND-09)" \
  --body "Closes FR-VND-09 for Phase 3 (PRD's own roadmap table lists it under Phase 3's exit criteria; PLAN-MISSION-3/7 had scoped it to Phase 7 only -- owner directed building it now, PRD wins). Adds a server-issued per-vendor API key (vendors.api_key, migration 0010), the first real vendor-facing route (GET /vendors/me/offers, identity resolved only from the key, never a client-supplied vendor_id), and one real isolation test at each of the three PRD-named levels: database (raw SQL), service (list_offers_by_vendor), route (real HTTP, deny-by-default on missing/unknown key). Does not resolve D-IDP or add RLS -- both recorded as explicitly out of scope in the plan doc."
```

Poll `gh pr checks <number>` every couple of minutes (do not block synchronously) until both Fast
gate and Full gate `pass`. Then `gh pr merge <number> --rebase --delete-branch`, then
`git fetch --prune`, `git checkout master`, `git reset --hard origin/master` (stash/pop any unrelated
uncommitted work first).

---

## Self-review notes

- **Spec coverage:** `FR-VND-09`'s exact wording ("route, service, database" levels) maps to Task 3
  (database), Task 4 (service), Task 6 (route) one-to-one. `INV-08` (deny-by-default) is covered by
  Task 6's two negative tests. `INV-11` (no silent fallback) is covered by `api_key` being `NOT NULL`
  with no default and never omitted from an INSERT.
- **No placeholders:** every migration, function, route, and test has real, complete code — no
  "add validation later" gaps.
- **Type consistency:** `store_vendor(conn, vendor) -> tuple[int, str]` (Task 2) is the exact shape
  every later task's call sites use (Tasks 2 Step 4, 4, 6). `list_offers_by_vendor(conn, *, vendor_id: int) -> list[dict[str, Any]]`
  (Task 2) is the exact shape Task 4 and the route in Task 5 call.
- **Doc-drift handling:** the plan does not silently pick a side of the PRD-vs-PLAN-MISSION conflict
  without recording it — Task 7 Step 3 explicitly logs the correction and flags `PLAN-MISSION-3.md`
  as needing a follow-up edit, rather than leaving future readers to rediscover the same conflict.
