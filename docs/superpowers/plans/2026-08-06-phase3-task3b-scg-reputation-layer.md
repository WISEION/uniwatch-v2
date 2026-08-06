# Phase 3, Task 3.B (SCG) — Reputation layer Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build `TENDER_INTELLIGENCE_SPEC.md` §6.2's "fourth layer of SCG" — `ReputationFact`, the
raw-fact record type that `INV-19` says all availability statuses and SCG prices must eventually be
weighted through. This is a prerequisite for §6.3 (Executable Availability, 3.C) and §6.4 (BOQ↔SCG
matching, 3.D), both of which name `INV-19` as load-bearing.

**Architecture:** Real reputation facts are supposed to come from Phase 4's Execution Ledger, market
data, and courts/debt records (§6.2's own text) — none of which exist yet (Phase 4 hasn't started).
Same synthetic-first pattern already used for the rest of Phase 3 (`ADR-0004`): build the real
`ReputationFact` domain model, a deterministic synthetic generator, and DB-enforced storage with TTL
expiry — proving the mechanism on synthetic data, not real vendor outcomes.

**Deliberately NOT built here, recorded not silently skipped:** the actual formula that collapses a
vendor's reputation facts into `INV-19`'s "trust coefficient" is not computed in this task. No source
document (PRD, master plan, `TENDER_INTELLIGENCE_SPEC.md`) supplies an approved weighting, and `INV-19`
explicitly ties the coefficient into "all SCG prices" — inventing a formula now would be inventing a
financial-adjacent number, the same category of thing `AGENTS.md` §2 hard-bans (`TBD-nn`/`D-nn`
placeholders instead of "reasonable" defaults). This is recorded as a new open decision (`D-VND-REP`)
in Task 5, not decided here. Tasks 3.C/3.D will need to either wait for that decision or consume the
raw facts directly (e.g. count of negative events) without collapsing them into one number — their own
call when they start.

Also deliberately not built: `ReputationFact`'s TTL "resets on vendor ownership change" behavior
(§6.2's own text) — there is no ownership-change concept anywhere in `packages/vendor`'s domain model
yet (`vendors` has no owner/parent-entity field). TTL here is a plain expiry
(`observed_at + ttl_days`), not the ownership-aware reset the spec describes. Recorded as a real gap
in Task 5, not implemented as if it were the same thing.

**Tech Stack:** Python 3.12 stdlib `random` (deterministic generator, same pattern as
`synthetic_provider.py`) — no new dependency.

## Global Constraints

- Every `ReputationFact` carries a mandatory `source_ref` (`INV-15`: "source_ref обязателен") — never
  omitted, never defaulted.
- Every fact is `data_realm="vendor-sandbox"`/`watermark="SYNTHETIC"` — same `ADR-0004` discipline as
  every other vendor-domain record in this phase; `vendor-production`/`REAL` exist as valid CHECK
  values but nothing in this codebase produces them yet.
- This migration (`0011`) bumps the real schema ledger version from 10 to 11 — every hardcoded `10`
  in existing tests/settings referring to *the current* schema version (not the deliberate mismatch
  value `99`) must be bumped to `11` in the same change (same pattern as the three prior version-bump
  follow-ups in `docs/reports/WORKLOG.md`).
- Every commit lands via a feature branch + PR + green CI (Fast + Full gate).
- Every requirement ID used must trace to `TENDER_INTELLIGENCE_SPEC.md` §6.2/§8, `INV-19`, `INV-15`,
  `INV-16`, `P313` — already-existing IDs. Do not invent a new one (the new open decision this task
  records, `D-VND-REP`, is recorded as an *open question*, not used as a requirement ID anywhere in
  code/tests/commits).

---

## Task 1: Migration `0011` — `vendor_reputation_facts`, and the schema-version ripple

**Files:**
- Create: `migrations/0011_vendor_reputation.sql`
- Modify: `packages/platform/settings.py:24`
- Modify: `tests/integration/test_migrations_runner.py:26,27,35,56,125-126`
- Modify: `tests/integration/test_api_tender_health.py:14,33`
- Modify: `tests/integration/test_api_vendor_health.py:15,34`
- Modify: `tests/contract/test_tender_vendor_contract.py:20,37`

**Interfaces:**
- Produces: `vendor_reputation_facts` table. Real schema ledger version `11`.

- [ ] **Step 1: Write the migration**

```sql
-- Reputation layer -- SCG's fourth layer (TENDER_INTELLIGENCE_SPEC.md
-- Section6.2, task 3.B, INV-19). Same explicit data_realm/watermark
-- discipline as migrations/0009_vendor_sandbox.sql -- only
-- 'vendor-sandbox'/'SYNTHETIC' rows are ever written by this task's code
-- (packages/vendor/synthetic_reputation.py); 'vendor-production'/'REAL'
-- exists in the CHECK constraint so the schema does not need a breaking
-- change once real onboarding (a separate legal/privacy/security gate,
-- out of this task's scope) needs it.

CREATE TABLE vendor_reputation_facts (
    id BIGSERIAL PRIMARY KEY,
    vendor_id BIGINT NOT NULL REFERENCES vendors (id),
    data_realm TEXT NOT NULL CHECK (data_realm IN ('vendor-sandbox', 'vendor-production')),
    watermark TEXT NOT NULL CHECK (watermark IN ('SYNTHETIC', 'REAL')),
    event_type TEXT NOT NULL,
    project_ref TEXT,
    source_ref TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    ttl_days INTEGER NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (
        (data_realm = 'vendor-sandbox' AND watermark = 'SYNTHETIC')
        OR (data_realm = 'vendor-production' AND watermark = 'REAL')
    )
);

CREATE INDEX vendor_reputation_facts_vendor_id_idx ON vendor_reputation_facts (vendor_id);
```

Save as `migrations/0011_vendor_reputation.sql`.

- [ ] **Step 2: Bump every hardcoded "current schema version" reference from 10 to 11**

`packages/platform/settings.py:24`:

```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "11")))
```

`tests/integration/test_migrations_runner.py`:
- Line 26: `assert versions == {1, 2, 3, 4, 5, 6, 7, 8, 9, 10}` → add `, 11`
- Line 27: `assert await runner.current_version() == 10` → `== 11`
- Line 35: `assert await runner.current_version() == 10` → `== 11`
- Line 56: `assert {m.version for m in applied} == {2, 3, 4, 5, 6, 7, 8, 9, 10}` → add `, 11`
- Line 125: `expected_version=10` → `expected_version=11`; line 126: `assert version == 10` → `== 11`

`tests/integration/test_api_tender_health.py`:
- Line 14: `expected_schema_version=10` → `expected_schema_version=11`
- Line 33: `assert body["schema_version"] == 10` → `== 11`
- (Line 37's `expected_schema_version=99` stays unchanged — deliberate mismatch value.)

`tests/integration/test_api_vendor_health.py`:
- Line 15: `expected_schema_version=10` → `expected_schema_version=11`
- Line 34: `assert body["schema_version"] == 10` → `== 11`

`tests/contract/test_tender_vendor_contract.py`:
- Line 20: `expected_schema_version=10` → `expected_schema_version=11`
- Line 37: `expected_schema_version=10` → `expected_schema_version=11`

- [ ] **Step 3: Run the affected tests to verify they pass**

Run: `python -m pytest tests/integration/test_migrations_runner.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py tests/contract/test_tender_vendor_contract.py -v`
Expected: all PASS.

- [ ] **Step 4: Commit**

```bash
git add migrations/0011_vendor_reputation.sql packages/platform/settings.py tests/integration/test_migrations_runner.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py tests/contract/test_tender_vendor_contract.py
git commit -m "feat(vendor): vendor_reputation_facts table (SCG 4th layer prep), bump schema version 10->11"
```

---

## Task 2: `reputation_model.py` — pure `ReputationFact` + event-type classification

**Files:**
- Create: `packages/vendor/reputation_model.py`
- Test: `tests/unit/test_reputation_model.py`

**Interfaces:**
- Produces: `ReputationFact` frozen dataclass; `POSITIVE_EVENT_TYPES`, `NEGATIVE_EVENT_TYPES`,
  `REPUTATION_EVENT_TYPES` tuples; `is_negative_event(event_type: str) -> bool` (raises `ValueError`
  on an unknown type).

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for ReputationFact (TENDER_INTELLIGENCE_SPEC.md Section6.2,
task 3.B). Event-type categories are taken directly from Section6.2's own
examples: "держит ли цену после выигрыша" (price_held_after_win / its
negative counterpart price_broken_after_win), "держит ли сроки"
(delivered_on_time / missed_deadline -- missed_deadline is P313's own
worked example), "качество/сертификаты/рекламации"
(certification_verified / quality_complaint), "финансовая дисциплина"
(financial_discipline_breach), "поведение под давлением... продал ли
чужую бронь в дефицит" (resold_reserved_stock_under_pressure)."""

from __future__ import annotations

import pytest

from packages.vendor.reputation_model import (
    NEGATIVE_EVENT_TYPES,
    POSITIVE_EVENT_TYPES,
    ReputationFact,
    is_negative_event,
)


def test_every_negative_event_type_is_classified_negative():
    assert all(is_negative_event(event_type) for event_type in NEGATIVE_EVENT_TYPES)


def test_every_positive_event_type_is_classified_positive():
    assert all(not is_negative_event(event_type) for event_type in POSITIVE_EVENT_TYPES)


def test_unknown_event_type_raises_instead_of_guessing():
    with pytest.raises(ValueError):
        is_negative_event("not-a-real-event-type")


def test_constructing_a_fact_with_an_unknown_event_type_raises():
    with pytest.raises(ValueError):
        ReputationFact(
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            vendor_name="Test Vendor",
            event_type="not-a-real-event-type",
            project_ref=None,
            source_ref="test",
            observed_at="2026-08-06T00:00:00+00:00",
            ttl_days=30,
        )


def test_a_valid_fact_constructs_cleanly():
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Test Vendor",
        event_type="missed_deadline",
        project_ref="project-x",
        source_ref="voice-note-2026-08-06",
        observed_at="2026-08-06T00:00:00+00:00",
        ttl_days=90,
    )
    assert fact.event_type == "missed_deadline"
    assert fact.project_ref == "project-x"
```

Save as `tests/unit/test_reputation_model.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_reputation_model.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.vendor.reputation_model'`.

- [ ] **Step 3: Write `reputation_model.py`**

```python
"""SCG's fourth layer -- reputation facts (TENDER_INTELLIGENCE_SPEC.md
Section6.2, task 3.B). Not a rating: facts about outcomes (held price
after winning a bid, missed a deadline, quality complaint, certification
verified, financial-discipline breach, resold reserved stock under
pressure during a shortage -- the categories Section6.2 names by
example). Pure dataclass, no DB, no network -- same shape as
vendor_model.py.

INV-19 says reputation is "a trust coefficient through which every
availability status and every SCG price passes". This module only
carries the raw facts (source_ref mandatory per INV-15/INV-16). The
formula that collapses facts into that coefficient is NOT computed here
-- see docs/decisions/OPEN-QUESTIONS.md (D-VND-REP): no source document
supplies an approved weighting, and INV-19 explicitly ties it into SCG
prices, so inventing one now would be inventing a financial-adjacent
number, not just plumbing."""

from __future__ import annotations

from dataclasses import dataclass

POSITIVE_EVENT_TYPES = (
    "price_held_after_win",
    "delivered_on_time",
    "certification_verified",
)
NEGATIVE_EVENT_TYPES = (
    "price_broken_after_win",
    "missed_deadline",
    "quality_complaint",
    "financial_discipline_breach",
    "resold_reserved_stock_under_pressure",
)
REPUTATION_EVENT_TYPES = POSITIVE_EVENT_TYPES + NEGATIVE_EVENT_TYPES


def is_negative_event(event_type: str) -> bool:
    if event_type in NEGATIVE_EVENT_TYPES:
        return True
    if event_type in POSITIVE_EVENT_TYPES:
        return False
    raise ValueError(f"unknown reputation event_type: {event_type!r}")


@dataclass(frozen=True)
class ReputationFact:
    data_realm: str
    watermark: str
    vendor_name: str
    event_type: str
    project_ref: str | None
    source_ref: str
    observed_at: str
    ttl_days: int

    def __post_init__(self) -> None:
        is_negative_event(self.event_type)  # raises ValueError on an unknown type
```

Save as `packages/vendor/reputation_model.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_reputation_model.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/reputation_model.py tests/unit/test_reputation_model.py
git commit -m "feat(vendor): ReputationFact domain model, event-type classification (SCG Section6.2, task 3.B)"
```

---

## Task 3: `synthetic_reputation.py` — deterministic generator

**Files:**
- Create: `packages/vendor/synthetic_reputation.py`
- Test: `tests/unit/test_synthetic_reputation.py`

**Interfaces:**
- Consumes: `ReputationFact`, `POSITIVE_EVENT_TYPES`, `NEGATIVE_EVENT_TYPES` (Task 2).
- Produces: `generate_reputation_facts(vendor_names: list[str], *, seed: int, as_of: str) -> list[ReputationFact]`.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the deterministic synthetic reputation-fact generator
(task 3.B). Same seed-determinism discipline as
tests/unit/test_synthetic_provider.py -- real reputation facts are
supposed to come from Phase 4's Execution Ledger (not built yet), so
this generator proves the ReputationFact mechanism on a synthetic mix of
reliable/unreliable vendor histories, not real vendor outcomes."""

from __future__ import annotations

from packages.vendor.reputation_model import NEGATIVE_EVENT_TYPES, POSITIVE_EVENT_TYPES
from packages.vendor.synthetic_reputation import generate_reputation_facts

AS_OF = "2026-08-06T00:00:00+00:00"
VENDOR_NAMES = ["Vendor A", "Vendor B", "Vendor C", "Vendor D"]


def test_same_seed_and_as_of_produce_identical_output():
    first = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    second = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    assert first == second


def test_different_seeds_produce_different_output():
    first = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    second = generate_reputation_facts(VENDOR_NAMES, seed=43, as_of=AS_OF)
    assert first != second


def test_produces_a_mix_of_reliable_and_unreliable_vendor_histories():
    facts = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    by_vendor: dict[str, list[str]] = {}
    for fact in facts:
        by_vendor.setdefault(fact.vendor_name, []).append(fact.event_type)

    assert len(by_vendor) == len(VENDOR_NAMES)
    has_a_reliable_vendor = any(all(event_type in POSITIVE_EVENT_TYPES for event_type in events) for events in by_vendor.values())
    has_an_unreliable_vendor = any(
        all(event_type in NEGATIVE_EVENT_TYPES for event_type in events) for events in by_vendor.values()
    )
    assert has_a_reliable_vendor
    assert has_an_unreliable_vendor


def test_every_fact_is_sandbox_realm_and_synthetic_watermarked():
    facts = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    assert all(fact.data_realm == "vendor-sandbox" and fact.watermark == "SYNTHETIC" for fact in facts)


def test_every_fact_carries_a_mandatory_source_ref():
    facts = generate_reputation_facts(VENDOR_NAMES, seed=42, as_of=AS_OF)
    assert all(fact.source_ref for fact in facts)
```

Save as `tests/unit/test_synthetic_reputation.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_synthetic_reputation.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.vendor.synthetic_reputation'`.

- [ ] **Step 3: Write `synthetic_reputation.py`**

```python
"""Deterministic synthetic reputation-fact generator (task 3.B, same
seed-determinism discipline as synthetic_provider.py). Real reputation
facts are supposed to come from Phase 4's Execution Ledger, market data,
and courts/debt records (TENDER_INTELLIGENCE_SPEC.md Section6.2) -- none
of which exist yet, so this generator produces a synthetic mix of
reliable/unreliable vendor histories to prove the ReputationFact
mechanism, not real vendor outcomes."""

from __future__ import annotations

import random

from .reputation_model import NEGATIVE_EVENT_TYPES, POSITIVE_EVENT_TYPES, ReputationFact


def generate_reputation_facts(vendor_names: list[str], *, seed: int, as_of: str) -> list[ReputationFact]:
    rng = random.Random(seed)
    facts: list[ReputationFact] = []
    for index, vendor_name in enumerate(vendor_names):
        # Deterministic split by input position, not a per-vendor random
        # draw -- keeps reproducibility independent of dict/set ordering.
        # Every third vendor gets an unreliable (negative-only) history;
        # the rest get a reliable (positive-only) one.
        reliable = index % 3 != 0
        event_pool = POSITIVE_EVENT_TYPES if reliable else NEGATIVE_EVENT_TYPES
        fact_count = rng.randint(1, 3)
        for _ in range(fact_count):
            facts.append(
                ReputationFact(
                    data_realm="vendor-sandbox",
                    watermark="SYNTHETIC",
                    vendor_name=vendor_name,
                    event_type=rng.choice(event_pool),
                    project_ref=None,
                    source_ref="synthetic-reputation-generator",
                    observed_at=as_of,
                    ttl_days=rng.choice([30, 90, 180]),
                )
            )
    return facts
```

Save as `packages/vendor/synthetic_reputation.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_synthetic_reputation.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/synthetic_reputation.py tests/unit/test_synthetic_reputation.py
git commit -m "feat(vendor): deterministic synthetic reputation-fact generator (SCG task 3.B)"
```

---

## Task 4: `reputation_store.py` — persistence + TTL-aware active-facts query

**Files:**
- Create: `packages/vendor/reputation_store.py`
- Test: `tests/integration/test_reputation_store.py`

**Interfaces:**
- Consumes: `ReputationFact` (Task 2), `generate_reputation_facts` (Task 3), `store_vendor` (existing,
  `packages/vendor/vendor_store.py`).
- Produces: `store_reputation_fact(conn, vendor_id: int, fact: ReputationFact) -> int`;
  `list_active_reputation_facts(conn, *, vendor_id: int, as_of: str) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write the failing test**

```python
"""Integration tests for reputation-fact persistence and TTL expiry
(task 3.B, TENDER_INTELLIGENCE_SPEC.md Section6.2). TTL here is a plain
observed_at + ttl_days expiry -- NOT the ownership-aware reset Section6.2
describes ("TTL: обнуляется при смене владельца вендора"), since
packages/vendor has no vendor-ownership concept yet. Recorded as a real
gap in docs/decisions/OPEN-QUESTIONS.md, not implemented as if it were
the same thing."""

from __future__ import annotations

from packages.vendor.reputation_model import ReputationFact
from packages.vendor.reputation_store import list_active_reputation_facts, store_reputation_fact
from packages.vendor.synthetic_reputation import generate_reputation_facts
from packages.vendor.vendor_model import Vendor
from packages.vendor.vendor_store import store_vendor


async def test_a_stored_fact_round_trips(engine):
    vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Rep Vendor", provider_type="synthetic", seed=1)
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Rep Vendor",
        event_type="missed_deadline",
        project_ref="project-x",
        source_ref="voice-note-2026-08-06",
        observed_at="2026-08-06T00:00:00+00:00",
        ttl_days=90,
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_reputation_fact(conn, vendor_id, fact)
        active = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of="2026-08-10T00:00:00+00:00")

    assert len(active) == 1
    assert active[0]["event_type"] == "missed_deadline"
    assert active[0]["project_ref"] == "project-x"
    assert active[0]["source_ref"] == "voice-note-2026-08-06"


async def test_a_fact_past_its_ttl_is_excluded(engine):
    vendor = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Stale Rep Vendor", provider_type="synthetic", seed=2
    )
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Stale Rep Vendor",
        event_type="quality_complaint",
        project_ref=None,
        source_ref="test",
        observed_at="2026-01-01T00:00:00+00:00",
        ttl_days=30,
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_reputation_fact(conn, vendor_id, fact)
        # 2026-08-06 is far past 2026-01-01 + 30 days.
        active = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of="2026-08-06T00:00:00+00:00")

    assert active == []


async def test_a_fact_exactly_at_its_ttl_boundary_is_excluded(engine):
    vendor = Vendor(
        data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Boundary Rep Vendor", provider_type="synthetic", seed=3
    )
    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="Boundary Rep Vendor",
        event_type="delivered_on_time",
        project_ref=None,
        source_ref="test",
        observed_at="2026-08-01T00:00:00+00:00",
        ttl_days=5,
    )

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(conn, vendor)
        await store_reputation_fact(conn, vendor_id, fact)
        # observed_at + ttl_days lands exactly on 2026-08-06T00:00:00 --
        # the boundary itself is not "still active" (strict >, not >=).
        active = await list_active_reputation_facts(conn, vendor_id=vendor_id, as_of="2026-08-06T00:00:00+00:00")

    assert active == []


async def test_facts_never_leak_across_vendors(engine):
    vendors, _offers = [], []
    facts_by_vendor: dict[str, list[ReputationFact]] = {}
    vendor_names = ["Cross Rep A", "Cross Rep B", "Cross Rep C"]
    generated = generate_reputation_facts(vendor_names, seed=7, as_of="2026-08-06T00:00:00+00:00")
    for name in vendor_names:
        facts_by_vendor[name] = [f for f in generated if f.vendor_name == name]

    async with engine.begin() as conn:
        vendor_ids: dict[str, int] = {}
        for name in vendor_names:
            vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name=name, provider_type="synthetic", seed=1)
            vendor_ids[name], _api_key = await store_vendor(conn, vendor)
        for name, facts in facts_by_vendor.items():
            for fact in facts:
                await store_reputation_fact(conn, vendor_ids[name], fact)

        one_vendor_id = vendor_ids[vendor_names[0]]
        active = await list_active_reputation_facts(conn, vendor_id=one_vendor_id, as_of="2026-08-06T00:00:00+00:00")

    assert all(row["vendor_id"] == one_vendor_id for row in active)
```

Save as `tests/integration/test_reputation_store.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_reputation_store.py -v`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.vendor.reputation_store'`.

- [ ] **Step 3: Write `reputation_store.py`**

```python
"""Reputation-fact persistence (task 3.B, TENDER_INTELLIGENCE_SPEC.md
Section6.2). Same explicit-realm discipline as vendor_store.py."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .reputation_model import ReputationFact


async def store_reputation_fact(conn: AsyncConnection, vendor_id: int, fact: ReputationFact) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendor_reputation_facts
                    (vendor_id, data_realm, watermark, event_type, project_ref, source_ref, observed_at, ttl_days)
                VALUES (:vendor_id, :data_realm, :watermark, :event_type, :project_ref, :source_ref,
                        :observed_at, :ttl_days)
                RETURNING id
                """
            ),
            {
                "vendor_id": vendor_id,
                "data_realm": fact.data_realm,
                "watermark": fact.watermark,
                "event_type": fact.event_type,
                "project_ref": fact.project_ref,
                "source_ref": fact.source_ref,
                "observed_at": datetime.fromisoformat(fact.observed_at),
                "ttl_days": fact.ttl_days,
            },
        )
    ).scalar_one()


async def list_active_reputation_facts(conn: AsyncConnection, *, vendor_id: int, as_of: str) -> list[dict[str, Any]]:
    """Facts whose TTL (observed_at + ttl_days) has not yet expired as of
    `as_of` -- an expired fact is excluded, never silently included past
    its TTL."""
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, vendor_id, data_realm, watermark, event_type, project_ref, source_ref,
                           observed_at, ttl_days
                    FROM vendor_reputation_facts
                    WHERE vendor_id = :vendor_id
                      AND observed_at + (ttl_days * interval '1 day') > :as_of
                    ORDER BY id
                    """
                ),
                {"vendor_id": vendor_id, "as_of": datetime.fromisoformat(as_of)},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

Save as `packages/vendor/reputation_store.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_reputation_store.py -v`
Expected: all 4 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/reputation_store.py tests/integration/test_reputation_store.py
git commit -m "feat(vendor): reputation-fact persistence, TTL-aware active-facts query (SCG task 3.B)"
```

---

## Task 5: WORKLOG, Open Questions (`D-VND-REP`), full gate, branch + PR + CI + merge

**Files:**
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

- [ ] **Step 1: Run the full gate**

```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```

- [ ] **Step 2: WORKLOG entry**

State: Phase 3, task 3.B (SCG reputation layer, `TENDER_INTELLIGENCE_SPEC.md` §6.2) built —
`ReputationFact` domain model, deterministic synthetic generator, DB-enforced storage with TTL expiry
(`vendor_reputation_facts`, migration `0011`, schema version 10→11). Explicitly record what was NOT
built: (1) the `INV-19` trust-coefficient formula (no source document supplies an approved weighting;
recorded as new open decision `D-VND-REP`, not invented); (2) TTL's "resets on vendor ownership
change" behavior (no ownership concept exists in `packages/vendor` yet — plain expiry only). Paste
real gate output.

- [ ] **Step 3: Open Questions entry — new decision `D-VND-REP`**

Record a new open decision, same shape as `D-TAX`: `D-VND-REP` — the formula that collapses a
vendor's `ReputationFact` history into `INV-19`'s "trust coefficient" (the number that reweights
Executable Availability statuses in 3.C and TCO risk-reserve in 3.D) is unresolved; blocks the
*numeric* half of 3.C/3.D, not their start (both tasks can consume raw `ReputationFact` rows directly
— e.g. counting negative events — without a collapsed coefficient, same incremental-slice discipline
already used elsewhere in this phase). Also record: this task's `ReputationFact` only models
`vendor_ref`-scoped facts, not `object_ref`-scoped ones (§8's entity definition allows either) —
`object_ref` reputation (e.g. customer reputation for Phase 4's Go/No-Go) is out of scope here, a
separate future task if Phase 4 needs it. Also record the ownership-change TTL-reset gap from Task 5
Step 2 here too, cross-referenced.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(vendor): record SCG reputation layer (task 3.B), new open decision D-VND-REP"
```

- [ ] **Step 5: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b phase3-task3b-scg-reputation-layer
git push -u origin phase3-task3b-scg-reputation-layer
gh pr create --base master --head phase3-task3b-scg-reputation-layer \
  --title "feat(vendor): SCG reputation layer, ReputationFact (TENDER_INTELLIGENCE_SPEC.md Section6.2, task 3.B)" \
  --body "Builds TENDER_INTELLIGENCE_SPEC.md Section6.2's fourth SCG layer: ReputationFact domain model, deterministic synthetic generator (real facts are supposed to come from Phase 4's Execution Ledger, which doesn't exist yet), DB-enforced storage with TTL expiry (migration 0011, schema version 10->11). Does NOT compute INV-19's trust-coefficient formula -- no source document supplies an approved weighting and INV-19 ties it to SCG prices, so that's recorded as a new open decision (D-VND-REP) in docs/decisions/OPEN-QUESTIONS.md rather than invented. Also does not implement the ownership-change TTL reset Section6.2 describes (no ownership concept exists in packages/vendor yet) -- recorded as a real gap, not silently approximated."
```

Poll `gh pr checks <number>` every couple of minutes (do not block synchronously) until both Fast
gate and Full gate `pass`. Then `gh pr merge <number> --rebase --delete-branch`, then
`git fetch --prune`, `git checkout master`, `git reset --hard origin/master` (stash/pop any unrelated
uncommitted work first).

---

## Self-review notes

- **Spec coverage:** §6.2's own deliverable (`ReputationFact`, source_ref/TTL discipline) is fully
  built. `INV-15`/`INV-16` (mandatory, addressable `source_ref`) covered by the model's mandatory
  field and the generator always setting it. `INV-19` is explicitly NOT computed — recorded, not
  silently approximated with an invented number.
- **No placeholders:** every model, generator, store function, and test has real, complete code.
- **Type consistency:** `ReputationFact` (Task 2) is the exact shape `generate_reputation_facts`
  (Task 3) produces and `store_reputation_fact`/`list_active_reputation_facts` (Task 4) consume.
- **Honest gap-recording:** two real gaps (the coefficient formula, the ownership-change TTL reset)
  are named explicitly in the plan's own Architecture section and again in Task 5's OPEN-QUESTIONS
  entry, not left for a future reader to rediscover.
