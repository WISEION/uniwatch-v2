# Phase 3, Task 3.A — Vendor synthetic sandbox (first slice) Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2/3 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the first real slice of `TENDER_INTELLIGENCE_SPEC.md` §6.1 / PRD `FR-VND-01..06,09`'s
vendor synthetic sandbox: the domain model, a single provider-adapter contract, one deterministic
synthetic provider covering 2 of the spec's 7 adverse cases, and a DB-level proof that synthetic/real
isolation (`FR-VND-06`, `ADR-0004`) is structurally enforced, not just a convention.

**Architecture:** `packages/vendor` (currently empty) gets its first real code, mirroring the pure/store
split already established in `packages/tender` (e.g. `signal_model.py` + `signals_store.py`):
`vendor_model.py` (pure `Vendor`/`Offer` dataclasses), `provider_contract.py` (the `FR-VND-04` adapter
interface every provider implements), `synthetic_provider.py` (a pure, deterministic generator, no DB),
`vendor_store.py` (async DB persistence). A new migration adds `vendors`/`vendor_offers` tables with
`data_realm`/`watermark` as first-class, DB-constrained columns from day one (`ADR-0004`'s own
requirement — adding this dimension later would need a backfill on data that must never mix realms).

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, PostgreSQL (CHECK constraints for isolation), stdlib
`random.Random(seed)` for determinism (no new dependency), pytest + pytest-asyncio, testcontainers Postgres.

## Global Constraints

- **Deliberately partial scope, matching FR-VND-04's own phase-level (not task-level) bar:** only ONE
  provider (`synthetic`) is built here. `FR-VND-04` requires "минимум два провайдера в Phase 3" —
  a second provider (e.g. CSV) is explicit future work for a later task in this phase, not this one.
- **Only 2 of `FR-VND-03`'s 7 adverse cases are built:** `stale_offer` (an offer whose `valid_until` is
  already before the reference `as_of` time) and `moq_conflict` (an offer whose MOQ exceeds its own
  capacity — a real, self-contradictory combination). The remaining 5 (mixed UOM, currency/VAT mismatch,
  capacity shortfall, expiring evidence, partial fulfillment) are explicit future work — record them as
  open in `docs/decisions/OPEN-QUESTIONS.md` (Task 6), do not stub them.
- **Strict isolation is enforced at the database layer, not just in application code**
  (`FR-VND-06`, `ADR-0004`): every `vendors`/`vendor_offers` row has a CHECK constraint tying
  `data_realm='vendor-sandbox'` to `watermark='SYNTHETIC'` (and the symmetric production/REAL pairing,
  even though no production path exists yet) — a mismatched insert must fail at the database, proven by
  a real test that attempts it and asserts the failure, not just an assertion on the happy path.
  `SyntheticProvider` hardcodes `data_realm`/`watermark` internally — they are never parameters a caller
  could override, so the provider is structurally incapable of producing anything else.
- **Determinism (`FR-VND-02`) means no ambient time or randomness inside the generator.** `SyntheticProvider.generate()`
  takes an explicit `seed: int` and an explicit `as_of: str` (ISO datetime) parameter — it never calls
  `datetime.now()`/`random.random()` internally. The same `(seed, as_of)` pair must always produce byte-
  identical output.
- **Route/service-level tenant isolation (`FR-VND-09`) is NOT built in this task** — there is no vendor
  HTTP API yet (`apps/api_vendor` only has the `/internal/ping` proof endpoint from ADR-0006's own task).
  Only the database-level isolation proof is in scope here; route/service-level isolation tests are
  future work once real vendor API endpoints exist. Record this explicitly, don't silently skip it.
- **Every commit lands via a feature branch + PR + green CI**, not a direct push to `master` — GitHub
  branch protection requires Fast gate + Full gate to pass first.
- Every requirement ID used must trace to `TENDER_INTELLIGENCE_SPEC.md` §6.1, `FR-VND-01..06`,
  `FR-VND-09`, `P312`, `ADR-0004` (all already-existing IDs) — do not invent a new one.

---

## Task 1: Migration — `vendors`/`vendor_offers` with DB-enforced realm/watermark pairing

**Files:**
- Create: `migrations/0009_vendor_sandbox.sql`
- Test: `tests/integration/test_vendor_sandbox_migration.py`

**Interfaces:**
- Produces: `vendors` table (`id`, `data_realm`, `watermark`, `name`, `provider_type`, `seed`,
  `created_at`) and `vendor_offers` table (`id`, `vendor_id` FK, `data_realm`, `watermark`, `material`,
  `price`, `currency`, `vat_rate`, `uom`, `uom_canonical_qty`, `moq`, `capacity`, `inventory`,
  `valid_from`, `valid_until`, `evidence_source`, `observed_at`, `adverse_case`, `created_at`) — both
  with a `CHECK` tying `data_realm` to `watermark`. Task 4's store functions insert into these tables.

- [ ] **Step 1: Write the failing test**

```python
"""Real proof that the vendors/vendor_offers schema exists and that its
realm/watermark CHECK constraint is a real database-level guarantee
(FR-VND-06, ADR-0004), not just an application-code convention."""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError


async def test_vendors_table_rejects_realm_watermark_mismatch(engine):
    async with engine.begin() as conn:
        # Correct pairing succeeds.
        await conn.execute(
            text(
                "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed) "
                "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Test Vendor', 'synthetic', 1)"
            )
        )

    async with engine.begin() as conn:
        try:
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed) "
                    "VALUES ('vendor-sandbox', 'REAL', 'Bad Vendor', 'synthetic', 1)"
                )
            )
        except IntegrityError:
            pass
        else:
            raise AssertionError("expected a realm/watermark mismatch to be rejected by the database")


async def test_vendor_offers_table_rejects_realm_watermark_mismatch(engine):
    async with engine.begin() as conn:
        vendor_id = (
            await conn.execute(
                text(
                    "INSERT INTO vendors (data_realm, watermark, name, provider_type, seed) "
                    "VALUES ('vendor-sandbox', 'SYNTHETIC', 'Test Vendor 2', 'synthetic', 2) RETURNING id"
                )
            )
        ).scalar_one()

    async with engine.begin() as conn:
        try:
            await conn.execute(
                text(
                    "INSERT INTO vendor_offers "
                    "(vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom, "
                    " uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until, "
                    " evidence_source, observed_at) "
                    "VALUES (:vendor_id, 'vendor-sandbox', 'REAL', 'rebar', 850.0, 'AZN', 18.0, 'ton', "
                    " 1.0, 5.0, 100.0, 80.0, now(), now(), 'test', now())"
                ),
                {"vendor_id": vendor_id},
            )
        except IntegrityError:
            pass
        else:
            raise AssertionError("expected a realm/watermark mismatch to be rejected by the database")
```

Save as `tests/integration/test_vendor_sandbox_migration.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_vendor_sandbox_migration.py -v` (Docker must be running)
Expected: FAIL — `relation "vendors" does not exist`.

- [ ] **Step 3: Write the migration**

```sql
-- Vendor synthetic sandbox (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-01,
-- FR-VND-02, FR-VND-05, ADR-0004): the domain model for supply-side
-- offers, with data_realm/watermark as first-class, DB-constrained
-- columns from this table's first migration -- adding this dimension
-- later would need a backfill on data that must never mix realms
-- (ADR-0004's own stated risk). Only 'vendor-sandbox'/'SYNTHETIC' rows
-- are ever written by this phase's code (packages/vendor/synthetic_provider.py) --
-- 'vendor-production'/'REAL' exists in the CHECK constraint now so the
-- schema does not need a breaking change when real vendor onboarding
-- (a separate legal/privacy/security gate, out of this task's scope)
-- eventually needs it.

CREATE TABLE vendors (
    id BIGSERIAL PRIMARY KEY,
    data_realm TEXT NOT NULL CHECK (data_realm IN ('vendor-sandbox', 'vendor-production')),
    watermark TEXT NOT NULL CHECK (watermark IN ('SYNTHETIC', 'REAL')),
    name TEXT NOT NULL,
    provider_type TEXT NOT NULL,
    seed INTEGER,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (data_realm = 'vendor-sandbox' AND watermark = 'SYNTHETIC')
        OR (data_realm = 'vendor-production' AND watermark = 'REAL')
    )
);

CREATE TABLE vendor_offers (
    id BIGSERIAL PRIMARY KEY,
    vendor_id BIGINT NOT NULL REFERENCES vendors (id),
    data_realm TEXT NOT NULL CHECK (data_realm IN ('vendor-sandbox', 'vendor-production')),
    watermark TEXT NOT NULL CHECK (watermark IN ('SYNTHETIC', 'REAL')),
    material TEXT NOT NULL,
    price NUMERIC NOT NULL,
    currency TEXT NOT NULL,
    vat_rate NUMERIC NOT NULL,
    uom TEXT NOT NULL,
    -- FR-VND-05 "UOM и конверсии": the offer's quantity expressed in a
    -- canonical unit, same intent as task 2.A's line-level UOM canonicalization.
    uom_canonical_qty NUMERIC NOT NULL,
    moq NUMERIC NOT NULL,
    capacity NUMERIC NOT NULL,
    inventory NUMERIC NOT NULL,
    valid_from TIMESTAMPTZ NOT NULL,
    valid_until TIMESTAMPTZ NOT NULL,
    evidence_source TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    -- NULL for a normal offer; a label (e.g. 'stale_offer', 'moq_conflict')
    -- for one of FR-VND-03's adverse cases -- never hidden, always tagged.
    adverse_case TEXT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (data_realm = 'vendor-sandbox' AND watermark = 'SYNTHETIC')
        OR (data_realm = 'vendor-production' AND watermark = 'REAL')
    )
);

CREATE INDEX vendor_offers_vendor_id_idx ON vendor_offers (vendor_id);
CREATE INDEX vendor_offers_data_realm_idx ON vendor_offers (data_realm);
```

Save as `migrations/0009_vendor_sandbox.sql`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_vendor_sandbox_migration.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add migrations/0009_vendor_sandbox.sql tests/integration/test_vendor_sandbox_migration.py
git commit -m "feat(vendor): vendors/vendor_offers schema, DB-enforced realm/watermark (FR-VND-06, task 3.A 1/6)"
```

---

## Task 2: `vendor_model.py` — pure `Vendor`/`Offer` dataclasses

**Files:**
- Create: `packages/vendor/vendor_model.py`
- Test: `tests/unit/test_vendor_model.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class Vendor` (`data_realm: str`, `watermark: str`, `name: str`,
  `provider_type: str`, `seed: int | None`) and `@dataclass(frozen=True) class Offer` (`vendor_name: str`,
  `data_realm: str`, `watermark: str`, `material: str`, `price: float`, `currency: str`,
  `vat_rate: float`, `uom: str`, `uom_canonical_qty: float`, `moq: float`, `capacity: float`,
  `inventory: float`, `valid_from: str`, `valid_until: str`, `evidence_source: str`, `observed_at: str`,
  `adverse_case: str | None`).

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the pure Vendor/Offer domain model (FR-VND-05)."""

from packages.vendor.vendor_model import Offer, Vendor


def test_vendor_holds_realm_and_watermark_explicitly():
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Test Vendor", provider_type="synthetic", seed=1)
    assert vendor.data_realm == "vendor-sandbox"
    assert vendor.watermark == "SYNTHETIC"


def test_offer_holds_every_fr_vnd_05_field():
    offer = Offer(
        vendor_name="Test Vendor",
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material="rebar-12mm",
        price=850.0,
        currency="AZN",
        vat_rate=18.0,
        uom="ton",
        uom_canonical_qty=1.0,
        moq=5.0,
        capacity=200.0,
        inventory=150.0,
        valid_from="2026-08-06T00:00:00+00:00",
        valid_until="2026-09-05T00:00:00+00:00",
        evidence_source="synthetic-generator",
        observed_at="2026-08-06T00:00:00+00:00",
        adverse_case=None,
    )
    assert offer.price == 850.0
    assert offer.currency == "AZN"
    assert offer.adverse_case is None
```

Save as `tests/unit/test_vendor_model.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_vendor_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.vendor.vendor_model'`.

- [ ] **Step 3: Write `vendor_model.py`**

```python
"""Vendor synthetic-sandbox domain model (TENDER_INTELLIGENCE_SPEC.md
§6.1, FR-VND-05, ADR-0004). Pure dataclasses, no DB, no network -- same
shape as packages/tender/signal_model.py.

`data_realm`/`watermark` are explicit fields on every Vendor/Offer, never
inferred -- INV-11's "no hidden fallback/synthetic state" applies here
exactly as it does to tender signals. Every instance this phase's code
constructs is `data_realm="vendor-sandbox"`/`watermark="SYNTHETIC"` --
`vendor-production`/`REAL` exist as valid values (matching the database
CHECK constraint) but nothing in this codebase produces them yet; real
vendor onboarding is a separate legal/privacy/security gate, out of scope
here."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Vendor:
    data_realm: str
    watermark: str
    name: str
    provider_type: str
    seed: int | None


@dataclass(frozen=True)
class Offer:
    vendor_name: str
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
    valid_from: str
    valid_until: str
    evidence_source: str
    observed_at: str
    adverse_case: str | None
```

Save as `packages/vendor/vendor_model.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_vendor_model.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/vendor_model.py tests/unit/test_vendor_model.py
git commit -m "feat(vendor): pure Vendor/Offer domain model (FR-VND-05, task 3.A 2/6)"
```

---

## Task 3: `provider_contract.py` — the FR-VND-04 adapter interface

**Files:**
- Create: `packages/vendor/provider_contract.py`
- Test: `tests/unit/test_provider_contract.py`

**Interfaces:**
- Consumes: `Vendor`/`Offer` (Task 2).
- Produces: `class SupplyProvider(Protocol)` with method
  `def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]`. Task 4's
  `SyntheticProvider` implements this exact signature.

- [ ] **Step 1: Write the failing test**

```python
"""Unit test for the FR-VND-04 provider adapter contract: any class
implementing `generate(seed, as_of) -> (vendors, offers)` satisfies the
Protocol, whether it's the synthetic provider or a future CSV/ERP/API/
portal one."""

from packages.vendor.provider_contract import SupplyProvider
from packages.vendor.vendor_model import Offer, Vendor


class _FakeProvider:
    def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        return [], []


def test_a_conforming_class_satisfies_the_protocol():
    provider: SupplyProvider = _FakeProvider()
    vendors, offers = provider.generate(seed=1, as_of="2026-08-06T00:00:00+00:00")
    assert vendors == []
    assert offers == []
```

Save as `tests/unit/test_provider_contract.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_provider_contract.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.vendor.provider_contract'`.

- [ ] **Step 3: Write `provider_contract.py`**

```python
"""Provider adapter contract (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04):
one interface every supply-side provider implements -- the synthetic
provider (this task) and future CSV/ERP/API/portal providers (later
tasks, FR-VND-04 requires at least 2 total in Phase 3, not necessarily
this one task). Downstream SCG/matching code (task 3.D, a later phase)
depends only on this Protocol, never on a concrete provider class."""

from __future__ import annotations

from typing import Protocol

from .vendor_model import Offer, Vendor


class SupplyProvider(Protocol):
    def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]: ...
```

Save as `packages/vendor/provider_contract.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_provider_contract.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/provider_contract.py tests/unit/test_provider_contract.py
git commit -m "feat(vendor): provider adapter contract (FR-VND-04, task 3.A 3/6)"
```

---

## Task 4: `synthetic_provider.py` — deterministic generator with 2 adverse cases

**Files:**
- Create: `packages/vendor/synthetic_provider.py`
- Test: `tests/unit/test_synthetic_provider.py`

**Interfaces:**
- Consumes: `Vendor`/`Offer` (Task 2), `SupplyProvider` (Task 3, structurally — no import needed since
  it's a Protocol, but `SyntheticProvider` must match its method signature exactly).
- Produces: `class SyntheticProvider` with `generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]`,
  returning exactly 3 vendors / 3 offers: one normal, one `adverse_case="stale_offer"`, one
  `adverse_case="moq_conflict"`.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the deterministic synthetic supply-side generator
(TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-01, FR-VND-02, FR-VND-03, P312)."""

from datetime import datetime

from packages.vendor.synthetic_provider import SyntheticProvider

AS_OF = "2026-08-06T00:00:00+00:00"


def test_every_generated_record_is_sandbox_realm_and_synthetic_watermarked():
    vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    assert vendors
    assert offers
    assert all(v.data_realm == "vendor-sandbox" and v.watermark == "SYNTHETIC" for v in vendors)
    assert all(o.data_realm == "vendor-sandbox" and o.watermark == "SYNTHETIC" for o in offers)


def test_same_seed_and_as_of_produce_identical_output():
    result_a = SyntheticProvider().generate(seed=42, as_of=AS_OF)
    result_b = SyntheticProvider().generate(seed=42, as_of=AS_OF)
    assert result_a == result_b


def test_different_seed_produces_different_price():
    vendors_a, offers_a = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    vendors_b, offers_b = SyntheticProvider().generate(seed=2, as_of=AS_OF)
    normal_a = next(o for o in offers_a if o.adverse_case is None)
    normal_b = next(o for o in offers_b if o.adverse_case is None)
    assert normal_a.price != normal_b.price


def test_covers_stale_offer_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    stale = next(o for o in offers if o.adverse_case == "stale_offer")
    as_of_dt = datetime.fromisoformat(AS_OF)
    valid_until_dt = datetime.fromisoformat(stale.valid_until)
    assert valid_until_dt < as_of_dt


def test_covers_moq_conflict_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    conflict = next(o for o in offers if o.adverse_case == "moq_conflict")
    assert conflict.moq > conflict.capacity


def test_normal_offer_has_no_adverse_case_and_is_not_stale_or_conflicted():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    normal = next(o for o in offers if o.adverse_case is None)
    as_of_dt = datetime.fromisoformat(AS_OF)
    assert datetime.fromisoformat(normal.valid_until) >= as_of_dt
    assert normal.moq <= normal.capacity
```

Save as `tests/unit/test_synthetic_provider.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_synthetic_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.vendor.synthetic_provider'`.

- [ ] **Step 3: Write `synthetic_provider.py`**

```python
"""Deterministic synthetic supply-side generator (TENDER_INTELLIGENCE_SPEC.md
§6.1, FR-VND-01, FR-VND-02, FR-VND-03, P312). Structurally incapable of
producing anything but sandbox-realm, SYNTHETIC-watermarked data --
data_realm/watermark are hardcoded here, never a parameter a caller could
override (FR-VND-06, ADR-0004: "strict isolation, not a soft label").

Determinism (FR-VND-02): `generate()` takes an explicit `seed` and an
explicit `as_of` reference time -- it never calls `datetime.now()` or the
module-level `random` singleton, so the same (seed, as_of) pair always
produces byte-identical output, regardless of when or how many times it's
called.

Covers 2 of FR-VND-03's 7 named adverse cases this task
(`stale_offer`, `moq_conflict`) -- the remaining 5 (mixed UOM,
currency/VAT mismatch, capacity shortfall, expiring evidence, partial
fulfillment) are real, un-invented future work, recorded in
docs/decisions/OPEN-QUESTIONS.md, not stubbed here."""

from __future__ import annotations

import random
from datetime import datetime, timedelta

from .vendor_model import Offer, Vendor


class SyntheticProvider:
    def generate(self, *, seed: int, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        rng = random.Random(seed)
        as_of_dt = datetime.fromisoformat(as_of)

        vendors: list[Vendor] = []
        offers: list[Offer] = []

        def _vendor(name: str) -> Vendor:
            vendor = Vendor(
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                name=name,
                provider_type="synthetic",
                seed=seed,
            )
            vendors.append(vendor)
            return vendor

        # Normal case: valid, non-expired offer, MOQ within capacity.
        normal_vendor = _vendor("Synthetic Rebar Supplier")
        offers.append(
            Offer(
                vendor_name=normal_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="rebar-12mm",
                price=round(rng.uniform(800.0, 900.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=5.0,
                capacity=200.0,
                inventory=150.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case=None,
            )
        )

        # Adverse case: stale_offer -- valid_until already before as_of.
        stale_vendor = _vendor("Synthetic Cement Supplier (stale)")
        offers.append(
            Offer(
                vendor_name=stale_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="cement-42.5",
                price=round(rng.uniform(150.0, 200.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=2.0,
                capacity=500.0,
                inventory=300.0,
                valid_from=(as_of_dt - timedelta(days=60)).isoformat(),
                valid_until=(as_of_dt - timedelta(days=5)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="stale_offer",
            )
        )

        # Adverse case: moq_conflict -- MOQ exceeds the vendor's own capacity.
        conflict_vendor = _vendor("Synthetic Aggregate Supplier (moq conflict)")
        offers.append(
            Offer(
                vendor_name=conflict_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="gravel-20mm",
                price=round(rng.uniform(30.0, 50.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="m3",
                uom_canonical_qty=1.0,
                moq=500.0,
                capacity=100.0,
                inventory=40.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="moq_conflict",
            )
        )

        return vendors, offers
```

Save as `packages/vendor/synthetic_provider.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_synthetic_provider.py -v`
Expected: all 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/synthetic_provider.py tests/unit/test_synthetic_provider.py
git commit -m "feat(vendor): deterministic synthetic provider, 2 adverse cases (FR-VND-01/02/03, task 3.A 4/6)"
```

---

## Task 5: `vendor_store.py` — persistence, real round-trip proof

**Files:**
- Create: `packages/vendor/vendor_store.py`
- Test: `tests/integration/test_vendor_store.py`

**Interfaces:**
- Consumes: `Vendor`/`Offer` (Task 2).
- Produces: `async def store_vendor(conn: AsyncConnection, vendor: Vendor) -> int`,
  `async def store_offer(conn: AsyncConnection, vendor_id: int, offer: Offer) -> int`,
  `async def list_offers_by_data_realm(conn: AsyncConnection, *, data_realm: str) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write the failing test**

```python
"""Real proof that the synthetic provider's output round-trips through
the database unchanged, and that a full sandbox-realm generation run
produces only sandbox/SYNTHETIC rows when queried back
(FR-VND-01, FR-VND-06)."""

from __future__ import annotations

from packages.vendor.synthetic_provider import SyntheticProvider
from packages.vendor.vendor_store import list_offers_by_data_realm, store_offer, store_vendor

AS_OF = "2026-08-06T00:00:00+00:00"


async def test_synthetic_generation_round_trips_through_the_database(engine):
    vendors, offers = SyntheticProvider().generate(seed=7, as_of=AS_OF)

    async with engine.begin() as conn:
        vendor_ids = {}
        for vendor in vendors:
            vendor_ids[vendor.name] = await store_vendor(conn, vendor)
        for offer in offers:
            await store_offer(conn, vendor_ids[offer.vendor_name], offer)

        rows = await list_offers_by_data_realm(conn, data_realm="vendor-sandbox")

    assert len(rows) == 3
    assert all(row["watermark"] == "SYNTHETIC" for row in rows)
    assert {row["adverse_case"] for row in rows} == {None, "stale_offer", "moq_conflict"}
    stale_row = next(row for row in rows if row["adverse_case"] == "stale_offer")
    assert stale_row["material"] == "cement-42.5"


async def test_no_production_realm_rows_exist_after_a_synthetic_run(engine):
    vendors, offers = SyntheticProvider().generate(seed=8, as_of=AS_OF)

    async with engine.begin() as conn:
        vendor_ids = {}
        for vendor in vendors:
            vendor_ids[vendor.name] = await store_vendor(conn, vendor)
        for offer in offers:
            await store_offer(conn, vendor_ids[offer.vendor_name], offer)

        production_rows = await list_offers_by_data_realm(conn, data_realm="vendor-production")

    assert production_rows == []
```

Save as `tests/integration/test_vendor_store.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_vendor_store.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.vendor.vendor_store'`.

- [ ] **Step 3: Write `vendor_store.py`**

```python
"""Vendor synthetic-sandbox persistence (FR-VND-01, FR-VND-06). Same
append-friendly, explicit-realm discipline as
packages/tender/signals_store.py -- every insert carries data_realm and
watermark explicitly (the database's own CHECK constraint,
migrations/0009_vendor_sandbox.sql, is the real enforcement; this module
does not re-validate it, it just never omits the columns)."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .vendor_model import Offer, Vendor


async def store_vendor(conn: AsyncConnection, vendor: Vendor) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendors (data_realm, watermark, name, provider_type, seed)
                VALUES (:data_realm, :watermark, :name, :provider_type, :seed)
                RETURNING id
                """
            ),
            {
                "data_realm": vendor.data_realm,
                "watermark": vendor.watermark,
                "name": vendor.name,
                "provider_type": vendor.provider_type,
                "seed": vendor.seed,
            },
        )
    ).scalar_one()


async def store_offer(conn: AsyncConnection, vendor_id: int, offer: Offer) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendor_offers
                    (vendor_id, data_realm, watermark, material, price, currency, vat_rate, uom,
                     uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                     evidence_source, observed_at, adverse_case)
                VALUES (:vendor_id, :data_realm, :watermark, :material, :price, :currency, :vat_rate, :uom,
                        :uom_canonical_qty, :moq, :capacity, :inventory, :valid_from, :valid_until,
                        :evidence_source, :observed_at, :adverse_case)
                RETURNING id
                """
            ),
            {
                "vendor_id": vendor_id,
                "data_realm": offer.data_realm,
                "watermark": offer.watermark,
                "material": offer.material,
                "price": offer.price,
                "currency": offer.currency,
                "vat_rate": offer.vat_rate,
                "uom": offer.uom,
                "uom_canonical_qty": offer.uom_canonical_qty,
                "moq": offer.moq,
                "capacity": offer.capacity,
                "inventory": offer.inventory,
                "valid_from": offer.valid_from,
                "valid_until": offer.valid_until,
                "evidence_source": offer.evidence_source,
                "observed_at": offer.observed_at,
                "adverse_case": offer.adverse_case,
            },
        )
    ).scalar_one()


async def list_offers_by_data_realm(conn: AsyncConnection, *, data_realm: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, vendor_id, data_realm, watermark, material, price, currency, vat_rate,
                           uom, uom_canonical_qty, moq, capacity, inventory, valid_from, valid_until,
                           evidence_source, observed_at, adverse_case
                    FROM vendor_offers WHERE data_realm = :data_realm ORDER BY id
                    """
                ),
                {"data_realm": data_realm},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

Note: SQLAlchemy binds `price`/`vat_rate`/etc. (Python `float`) to `NUMERIC` columns automatically —
no manual cast needed, same as existing `signals_store.py` patterns for other column types.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_vendor_store.py -v`
Expected: both PASS.

- [ ] **Step 5: Re-run the full unit + integration suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`
Expected: all previously-passing tests still pass, plus this task's new tests.

- [ ] **Step 6: Commit**

```bash
git add packages/vendor/vendor_store.py tests/integration/test_vendor_store.py
git commit -m "feat(vendor): synthetic-sandbox persistence, real round-trip proof (FR-VND-01/06, task 3.A 5/6)"
```

---

## Task 6: WORKLOG, Open Questions, full gate, branch + PR + CI + merge

**Files:**
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

- [ ] **Step 1: Run the full gate**

Run:
```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```
Expected: 0 failures, 0 issues, `PASS: v1 untouched`.

- [ ] **Step 2: WORKLOG entry**

Append to `docs/reports/WORKLOG.md`, matching the existing entries' style (`**Сделано:**`, `**Вывод
полного прогона (Fast+Full gate):**`, `**Дальше:**`, `**Блокеры:**`). Content to include, plainly:

- First real code in `packages/vendor` — starts Phase 3 (`TENDER_INTELLIGENCE_SPEC.md` §6.1, task 3.A).
  Owner chose Phase 3 (Vendor/SCG) over widening Phase 2 signal coverage; chose the synthetic-sandbox
  path first since no real vendor inputs (photos/voice/ERP folders) are available in this session.
- `packages/vendor/vendor_model.py` (pure `Vendor`/`Offer`, `FR-VND-05`), `provider_contract.py`
  (`FR-VND-04`'s one-adapter-interface), `synthetic_provider.py` (deterministic generator, `FR-VND-01/02`),
  `vendor_store.py` (persistence), `migrations/0009_vendor_sandbox.sql` (`vendors`/`vendor_offers`,
  `data_realm`/`watermark` DB-CHECK-enforced pairing from day one, per `ADR-0004`).
- Covers exactly 2 of `FR-VND-03`'s 7 named adverse cases (`stale_offer`, `moq_conflict`) plus one
  normal case — proven deterministic (same seed+as_of → identical output) and proven isolated (a
  mismatched realm/watermark insert is rejected by the database itself, not just application code).
- What was deliberately NOT built and why: the second provider `FR-VND-04` requires (CSV, deferred to a
  later Phase 3 task); the other 5 adverse cases (mixed UOM, currency/VAT mismatch, capacity shortfall,
  expiring evidence, partial fulfillment — real, un-invented future work); route/service-level tenant
  isolation (`FR-VND-09`) — no vendor HTTP API exists yet beyond `apps/api_vendor`'s existing
  `/internal/ping` proof endpoint (ADR-0006), so only DB-level isolation is proven here.
- Files: `packages/vendor/vendor_model.py`, `provider_contract.py`, `synthetic_provider.py`,
  `vendor_store.py` (all new), `migrations/0009_vendor_sandbox.sql` (new). Tests:
  `tests/unit/test_vendor_model.py` (2), `tests/unit/test_provider_contract.py` (1),
  `tests/unit/test_synthetic_provider.py` (6), `tests/integration/test_vendor_sandbox_migration.py` (2),
  `tests/integration/test_vendor_store.py` (2).
- Paste the actual `pytest`/`ruff`/`mypy`/`check_v1_untouched.py` output from Step 1 — do not fabricate
  pass counts.

- [ ] **Step 3: Open Questions entry**

Append to `docs/decisions/OPEN-QUESTIONS.md`, same format as existing entries (`**Context:**`,
`**Deviation/assumption:**`, `**Consequence that must not be silently dropped:**`, `**Owner follow-up
needed:**`). Content:

- Context: `TENDER_INTELLIGENCE_SPEC.md` §6.1 / PRD `FR-VND-01..06,09` specify the full vendor synthetic
  sandbox: 2+ providers, all 7 adverse cases, and route/service/DB-level tenant isolation tests. This
  task built one provider, 2 adverse cases, and DB-level isolation only.
- Deviation/assumption: no real vendor inputs (photos, voice notes, ERP/folder access) exist in this
  session, so task 3.A's actual "салфеточный ingestion" (napkin ingestion via OCR/ASR) couldn't start —
  owner chose to build the synthetic-sandbox engine first instead (explicitly allowed to run
  before/parallel to real ingestion per `TENDER_INTELLIGENCE_SPEC.md` §6's own text). Scope further
  trimmed to 1 provider / 2 adverse cases / DB-only isolation as the first slice, not the whole
  `FR-VND-01..06,09` bar — matching this project's established incremental-slice discipline.
- Consequence: `SyntheticProvider` alone does not yet satisfy `FR-VND-04`'s "minimum two providers"
  phase-level bar, and the adverse-case coverage is real but partial (2/7) — any downstream work (e.g.
  task 3.D matching) that assumes full adverse-case coverage exists must not assume the other 5 cases
  are handled. Route/service-level tenant isolation (`FR-VND-09`) remains unbuilt until a real vendor
  HTTP API exists.
- Owner follow-up needed: No, not blocking — the trimmed scope was the owner's own choice for this
  slice. Real vendor inputs (for the actual napkin-ingestion pipeline, OCR/ASR tech choice) and the
  second provider/remaining adverse cases/route-level isolation are open future work, not urgent.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(vendor): record synthetic-sandbox slice scope and real gaps (task 3.A 6/6)"
```

- [ ] **Step 5: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b phase3-task3a-vendor-synthetic-sandbox
git push -u origin phase3-task3a-vendor-synthetic-sandbox
gh pr create --base master --head phase3-task3a-vendor-synthetic-sandbox \
  --title "feat(vendor): synthetic sandbox — domain model, one provider, 2 adverse cases (Phase 3, task 3.A)" \
  --body "First real code in packages/vendor: Vendor/Offer domain model (FR-VND-05), provider adapter contract (FR-VND-04), one deterministic synthetic provider covering 2/7 adverse cases (FR-VND-01/02/03), and a real DB-level proof that realm/watermark isolation is enforced by the database itself (FR-VND-06, ADR-0004), not just application code. Deliberately trimmed scope, recorded in docs/decisions/OPEN-QUESTIONS.md: second provider, remaining 5 adverse cases, and route/service-level tenant isolation (FR-VND-09) are explicit future work."
```

Poll `gh pr checks <number>` every couple of minutes (do not block synchronously) until both `Fast
gate` and `Full gate` report `pass` — `live-fetch` is expected to `fail` and is not required. Then:

```bash
gh pr merge <number> --rebase --delete-branch
git fetch --prune
git checkout master
git reset --hard origin/master
```

(If there are unrelated uncommitted changes in the working tree at this point, `git stash push -u`
before the reset and `git stash pop` after.)

---

## Self-review notes

- **Spec coverage:** `FR-VND-01` (sandbox + watermark), `FR-VND-02` (deterministic seed), `FR-VND-03`
  (2/7 adverse cases, rest explicitly deferred), `FR-VND-04` (one adapter interface, second provider
  deferred), `FR-VND-05` (full field set), `FR-VND-06` (DB-enforced isolation) each map to a task above.
  `FR-VND-09` (route/service isolation) is explicitly out of scope, recorded not silently skipped (Task 6).
- **No placeholders:** every step has real, complete code — the adverse cases are concretely defined
  (`stale_offer`: `valid_until < as_of`; `moq_conflict`: `moq > capacity`), not left as "add more adverse
  cases later" without specifics for the two that ARE built.
- **Type consistency:** `Vendor`/`Offer` (Task 2) are consumed unchanged by `SupplyProvider` (Task 3),
  `SyntheticProvider` (Task 4), and `vendor_store.py` (Task 5) — same field names throughout.
