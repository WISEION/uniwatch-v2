# Phase 4, Task 4.D — Calibration Loop (measurement substrate) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the Execution Ledger → Decision Core feedback loop by recording the facts calibration needs — public tender outcome, our submitted price, loss post-mortem, persisted forecast cards, and the read path for the currently write-only overhead buffer — without inventing a single weight, threshold, or TTL.

**Architecture:** Every input this task adds is either (a) a fact a human already knows and enters directly (outcome, our submitted price, winner, loss reason), following the `GoNoGoInputs`/napkin precedent (ADR-0005: a human's assessment gets a durable queryable home, nothing is scored for them), or (b) arithmetic over data already in the database (price deltas, category counts, observed lag in days). No coefficient, weight, probability, or TTL number is introduced anywhere. All new tables are append-only, consistent with `execution_facts`/`decisions`.

**Tech Stack:** Python 3.12, FastAPI, SQLAlchemy 2.0 async + asyncpg, Postgres, pytest + pytest-asyncio + testcontainers. No new dependency.

---

## Why this scope, and not the spec's literal §7.4

`TENDER_INTELLIGENCE_SPEC.md` §7.4 asks for a *calibration* loop: recalibrated DFE signal weights, per-buyer TTL/horizons, and the historical overhead buffer applied as an overlay onto each new 4.A estimate. **None of that is buildable today**, and building it anyway would violate `AGENTS.md`'s hard bans. Verified against the repo, not assumed:

| §7.4 asks for | Why it cannot be built now |
| --- | --- |
| Winner price vs our market-cost estimate | No table, column, model, connector or fixture stores any tender outcome. `signals.value->'awarded_participant_name'` (`packages/tender/design_tender_signal.py:57`) is the only trace and has **only ever been observed `null`** — every capture used `EventStatus=1` (open) and which value means "awarded" is undecoded (`fixtures/tender-snapshots/etender/MANIFEST.md:52`). `AwardedparticipantName`/`Voen` exist in `packages/tender/etender_contract.py:85` only as *filter query keys*, never response fields. Even for an awarded item, `MANIFEST.md:33` records the events-list resource has **no monetary field at all**. |
| Recalibrated DFE signal weights | `signals` has no weight column (`migrations/0008_signals.sql:8-27`) though spec §8 names one; no weight constant exists in code. Blocked on `TBD-TIS-02`, which spec §5.3 says needs a ≥30-tender backtest first. Hard ban #2. |
| Per-buyer TTL / horizons | `ttl_class` is three hardcoded *string labels* (`signal_model.py:68`, `design_tender_signal.py:64`, `procurement_plan_signal.py:39`), each annotated `TBD-TIS-01`. No decay arithmetic, no numeric TTL, no Object/buyer entity. Hard ban #2. |
| Overhead buffer applied as a cost overlay | `overhead_buffer_contributions.fact_count` is a raw count. `migrations/0016_execution_ledger.sql:53-57` deferred the weighting formula to this task with **no source supplying it**. Hard ban #2. |

**What this task builds instead: the measurement substrate.** Everything above is blocked on the same root cause — *the system has never recorded what actually happened*. This task starts that recording, so the calibration decisions become answerable later from real data instead of guesses. Concretely, after this task:

1. Outcomes and our submitted price exist as durable facts → the winner-vs-us comparison has both operands.
2. Loss reasons are typed using **the spec's own three categories** (§7.4 names them verbatim; see Task 2) → "разбор проигрышей" is a real queryable artifact.
3. Forecast cards are persisted with a human-confirmed link to the tender they predicted → the ≥30-tender backtest that unblocks `TBD-TIS-02` becomes *possible* (it is impossible today: no `forecasts` table exists, cards are computed on the fly and discarded).
4. The overhead buffer becomes readable → a human can see the accumulated counts, even though no formula weights them.

**Explicit non-goals (do NOT build; each would break a hard ban):** any signal weight; any numeric TTL or decay; any cost-weighted overhead overlay; any auto-derived loss reason; any automatic forecast→tender matching (see Task 5's rationale); any eTender award-connector work (needs a real network capture session first — same discipline as the Q&A gap in `docs/decisions/OPEN-QUESTIONS.md`); `D-VND-REP`'s trust coefficient.

---

## Global Constraints

Every task's requirements implicitly include this section.

- **Hard ban #2** — never invent a number for anything tagged `TBD-nn`/`D-nn`. This task introduces **zero** new numeric constants. If a step seems to need one, stop and record the gap instead.
- **Hard ban #3** — no silent fallbacks. `missing`/`incomplete` states are always surfaced. Specifically: a price comparison over partially-covered BOQ lines must always report its coverage alongside the delta, never a bare number (see Task 4).
- **Hard ban #4** — ingestion/derived output never overwrites a human decision. Every new table here is either a human-entered fact or a derived read; nothing derived is written into a decision.
- **Append-only** — no `UPDATE`/`DELETE` statement against any table this task creates, matching `execution_facts`/`decisions`. Correction is a new row, not an edit.
- **INV-15/INV-16** — every fact carries a `source_ref`; raw evidence is addressable. Human-entered outcomes carry a mandatory free-text `source_ref` naming where the human saw it.
- **ADR-0001 boundaries** — `packages/decision` may not import `packages/vendor`; vendor data only via `packages/contracts/vendor_api.py`. Forecast-snapshot code is tender-domain and lives in `packages/tender`.
- **ADR-0006** — `apps/api_tender` and `apps/api_vendor` are separate processes. This task adds routes to `apps/api_tender` only.
- **Migrations** — never edit an applied migration (checksum guard). New file `migrations/0017_calibration_loop.sql`, and `EXPECTED_SCHEMA_VERSION` default bumps `16` → `17` in `packages/platform/settings.py:24`.
- **Timestamps** — asyncpg binds `TIMESTAMPTZ` by native `datetime`, not ISO string: always `datetime.fromisoformat(...)` at the bind site, matching `packages/decision/execution_ledger_store.py:46`.
- **Routes** — `require_permission(...)` deny-by-default on every route; `ApiError` (never bare `HTTPException`); `write_audit_log` on every mutation.
- **Gates (run before considering any task done):** `python -m pytest tests/ -q -m "not live_network"`, `python -m ruff format --check .`, `python -m ruff check .`, `python -m mypy packages apps`, `python tools/check_v1_untouched.py`.

---

## File Structure

**Create:**
- `migrations/0017_calibration_loop.sql` — four append-only tables: `tender_outcomes`, `tender_loss_reasons`, `forecast_card_snapshots`, `forecast_card_tender_links`.
- `packages/decision/calibration_model.py` — `TenderOutcome`, `LossReason` dataclasses + the two allowed-value tuples, validating in `__post_init__` (same shape as `decision_model.py`).
- `packages/decision/calibration_store.py` — persistence + queries for outcomes and loss reasons; read path for `overhead_buffer_contributions`.
- `packages/decision/calibration_summary.py` — pure functions: price delta vs coverage, loss-reason rollup. No DB, no network (same shape as `execution_ledger_summary.py`).
- `packages/tender/forecast_snapshot_store.py` — persist a `ForecastCard` as an immutable snapshot; record a human-confirmed snapshot→tender link; derive observed lag.
- `apps/api_tender/routers/calibration.py` — outcome/loss-reason/overhead/calibration routes.
- Tests: `tests/unit/test_calibration_model.py`, `tests/unit/test_calibration_summary.py`, `tests/integration/test_calibration_store.py`, `tests/integration/test_calibration_api.py`, `tests/integration/test_forecast_snapshot_store.py`.

**Modify:**
- `packages/platform/settings.py:24` — `EXPECTED_SCHEMA_VERSION` default `16` → `17`.
- `apps/api_tender/main.py` — register the new router(s).

---

### Task 1: Migration + outcome/loss-reason model and store

**Files:**
- Create: `migrations/0017_calibration_loop.sql`, `packages/decision/calibration_model.py`, `packages/decision/calibration_store.py`
- Modify: `packages/platform/settings.py:24`
- Test: `tests/unit/test_calibration_model.py`, `tests/integration/test_calibration_store.py`

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `OUTCOME_TYPES`, `LOSS_REASONS`, `TenderOutcome`, `LossReason` (from `calibration_model`); `store_tender_outcome(conn, outcome) -> int`, `load_tender_outcome(conn, *, tender_id) -> dict[str, Any] | None`, `store_loss_reason(conn, reason, *, tender_outcome_id) -> int`, `list_loss_reasons_by_outcome(conn, *, tender_outcome_id) -> list[dict[str, Any]]`, `list_overhead_buffer_contributions(conn, *, tender_id) -> list[dict[str, Any]]` (from `calibration_store`).

**Allowed-value rationale — read before writing the `CHECK` constraints.** Spec §7.4 names exactly three loss reasons verbatim: *"проиграли дешёвому доступу конкурента"* → `competitor_cheap_access`, *"демпингу"* → `dumping`, *"«рисунку»"* → `drawn_tender`. These three are **sourced, not invented**. Two additions are made deliberately and must be recorded in `OPEN-QUESTIONS.md` at close-out (Task 5):
- `other` on `loss_reason`, with a mandatory non-empty `note`. Forcing a real loss into one of three categories would fabricate a cause and poison the very loss analysis §7.4 wants.
- `cancelled` on `outcome`, alongside `won`/`lost`. A cancelled tender is a real observable state; recording it as `lost` would be a lie that corrupts loss statistics.

Neither is a number and neither is a `TBD-nn` substitution — they are honesty escape hatches, which is the opposite of a silent fallback.

- [ ] **Step 1: Write the failing model test**

```python
# tests/unit/test_calibration_model.py
import pytest

from packages.decision.calibration_model import LOSS_REASONS, OUTCOME_TYPES, LossReason, TenderOutcome


def _outcome(**overrides):
    base = dict(
        tender_id=1,
        outcome="lost",
        our_submitted_amount="120000.00",
        winner_name="Rival LLC",
        winner_amount="98000.00",
        currency="AZN",
        announced_at="2026-08-01T00:00:00+00:00",
        source_ref="etender public award page, screenshot in project folder",
        entered_by="pm@unico.az",
        entered_at="2026-08-02T00:00:00+00:00",
    )
    return TenderOutcome(**{**base, **overrides})


def test_allowed_values_are_exactly_the_sourced_sets():
    assert OUTCOME_TYPES == ("won", "lost", "cancelled")
    assert LOSS_REASONS == ("competitor_cheap_access", "dumping", "drawn_tender", "other")


def test_unknown_outcome_raises_rather_than_being_accepted():
    with pytest.raises(ValueError, match="unknown outcome"):
        _outcome(outcome="probably_lost")


def test_source_ref_is_mandatory_because_INV_15_requires_provenance():
    with pytest.raises(ValueError, match="source_ref"):
        _outcome(source_ref="   ")


def test_a_won_outcome_needs_no_winner_fields():
    assert _outcome(outcome="won", winner_name=None, winner_amount=None).outcome == "won"


def test_unknown_loss_reason_raises():
    with pytest.raises(ValueError, match="unknown loss_reason"):
        LossReason(loss_reason="bad_luck", note="n", entered_by="a", entered_at="2026-08-02T00:00:00+00:00")


def test_other_loss_reason_requires_a_note_so_the_cause_is_never_blank():
    with pytest.raises(ValueError, match="note"):
        LossReason(loss_reason="other", note="  ", entered_by="a", entered_at="2026-08-02T00:00:00+00:00")
```

- [ ] **Step 2: Run it and confirm it fails**

Run: `python -m pytest tests/unit/test_calibration_model.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'packages.decision.calibration_model'`

- [ ] **Step 3: Write the model**

```python
# packages/decision/calibration_model.py
"""Calibration-loop domain model (Phase 4, task 4.D,
TENDER_INTELLIGENCE_SPEC.md Section7.4, P319). Pure dataclasses, no DB --
packages/decision/calibration_store.py persists these.

Every field here is a fact a human already knows and enters directly (who
won, for how much, what we submitted, why we think we lost). Nothing is
scored, weighted, or derived: Section7.4's actual calibration outputs
(signal weights, per-buyer TTL/horizons, the overhead-buffer cost overlay)
all remain blocked on TBD-TIS-01/TBD-TIS-02 and are deliberately NOT
produced here (AGENTS.md hard ban #2). This module only gives the inputs a
durable, queryable home -- the same role decision_model.py's GoNoGoInputs
plays for Go/No-Go.

LOSS_REASONS' first three values are Section7.4's own verbatim categories
("проиграли дешёвому доступу конкурента" / "демпингу" / "«рисунку»"), not
an invented taxonomy. `other` is added deliberately, with a mandatory note:
forcing a real loss into one of three categories would fabricate a cause
and corrupt the loss analysis Section7.4 exists to enable. `cancelled` is
added to OUTCOME_TYPES for the same reason -- recording a cancelled tender
as `lost` would be a lie. Both additions are recorded in
docs/decisions/OPEN-QUESTIONS.md, not made silently."""

from __future__ import annotations

from dataclasses import dataclass

OUTCOME_TYPES = ("won", "lost", "cancelled")
LOSS_REASONS = ("competitor_cheap_access", "dumping", "drawn_tender", "other")


@dataclass(frozen=True)
class TenderOutcome:
    tender_id: int
    outcome: str
    our_submitted_amount: str | None
    winner_name: str | None
    winner_amount: str | None
    currency: str | None
    announced_at: str | None
    source_ref: str
    entered_by: str
    entered_at: str

    def __post_init__(self) -> None:
        if self.outcome not in OUTCOME_TYPES:
            raise ValueError(f"unknown outcome: {self.outcome!r}")
        # INV-15/INV-16: a fact with no provenance is not a fact. A
        # human-entered outcome cannot point at a raw_snapshot (nothing
        # fetched it), so free text naming where the human saw it is the
        # honest minimum -- but it must not be blank.
        if not self.source_ref.strip():
            raise ValueError("source_ref must be non-empty (INV-15)")


@dataclass(frozen=True)
class LossReason:
    loss_reason: str
    note: str
    entered_by: str
    entered_at: str

    def __post_init__(self) -> None:
        if self.loss_reason not in LOSS_REASONS:
            raise ValueError(f"unknown loss_reason: {self.loss_reason!r}")
        if self.loss_reason == "other" and not self.note.strip():
            raise ValueError("loss_reason 'other' requires a non-empty note")
```

- [ ] **Step 4: Run the model test and confirm it passes**

Run: `python -m pytest tests/unit/test_calibration_model.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Write the migration**

```sql
-- migrations/0017_calibration_loop.sql
-- Calibration loop measurement substrate (Phase 4, task 4.D,
-- TENDER_INTELLIGENCE_SPEC.md Section7.4, P319).
--
-- This migration deliberately adds NO weight, coefficient, TTL, or
-- probability column. Section7.4's actual calibration outputs remain
-- blocked on TBD-TIS-02 (signal weights, confidence tiers) and TBD-TIS-01
-- (numeric TTL per fact class); inventing either would violate AGENTS.md
-- hard ban #2. What this migration adds is the record of WHAT ACTUALLY
-- HAPPENED, which is the missing input those decisions are blocked on --
-- nothing in this codebase has ever stored a tender outcome.
--
-- All four tables are append-only: application code issues no UPDATE or
-- DELETE against them (same discipline as execution_facts / decisions).
-- A correction is a new row, never an edit.

-- Public outcome of a tender, entered by a human. There is no connector:
-- no eTender award/result endpoint has been captured, and the events-list
-- resource carries no monetary field at all (fixtures/tender-snapshots/
-- etender/MANIFEST.md) -- so a human who has seen the public award enters
-- it, same zero-entry-threshold discipline as INV-18's napkin ingestion.
--
-- our_submitted_amount is the first place in this codebase to store OUR
-- OWN price. decisions (0014) records type/conditions/deadline/
-- justification with no amount, so "winner price vs us" previously had
-- neither operand.
--
-- Amounts are NUMERIC and nullable: a `won` outcome needs no winner
-- fields, and a human may know the winner's name but not their price
-- (MANIFEST.md records the public list resource exposes the winner's name
-- and VOEN but no money). A missing amount stays NULL and is surfaced as
-- missing downstream -- never coerced to 0 (hard ban #3).
CREATE TABLE tender_outcomes (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    outcome TEXT NOT NULL CHECK (outcome IN ('won', 'lost', 'cancelled')),
    our_submitted_amount NUMERIC,
    winner_name TEXT,
    winner_amount NUMERIC,
    currency TEXT,
    announced_at TIMESTAMPTZ,
    -- INV-15/INV-16: free text naming where the human saw this outcome.
    -- Not a raw_snapshot reference: nothing fetched it.
    source_ref TEXT NOT NULL,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- One outcome per tender. Append-only means a correction is a new row, so
-- this is a partial unique index rather than a plain UNIQUE: it lets the
-- route reject a duplicate loudly (409) instead of silently accumulating
-- two contradictory outcomes for one tender.
CREATE UNIQUE INDEX tender_outcomes_tender_uniq ON tender_outcomes (tender_id);

-- Section7.4's "разбор проигрышей" -- the spec calls it the single most
-- informative artifact. The first three loss_reason values are the spec's
-- own verbatim categories; 'other' exists so a real cause outside them is
-- never misfiled (the route enforces a non-empty note for it).
--
-- A separate table, not a column on tender_outcomes: a loss can have more
-- than one contributing cause, and each carries its own note and author.
CREATE TABLE tender_loss_reasons (
    id BIGSERIAL PRIMARY KEY,
    tender_outcome_id BIGINT NOT NULL REFERENCES tender_outcomes (id),
    loss_reason TEXT NOT NULL CHECK (
        loss_reason IN ('competitor_cheap_access', 'dumping', 'drawn_tender', 'other')
    ),
    note TEXT NOT NULL,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX tender_loss_reasons_outcome_idx ON tender_loss_reasons (tender_outcome_id);

-- Persisted forecast card (task 2.C/2.D built ForecastCard as a pure
-- in-memory assembly -- packages/tender/forecast_card.py -- computed on
-- demand and discarded, so no forecast has ever been retained). Without
-- retention, spec Section5.3/P310's ">=30 already-published tenders"
-- backtest is impossible, and that backtest is exactly what TBD-TIS-02 is
-- blocked on. This table starts the retention; it computes nothing.
--
-- Columns mirror ForecastCard's own fields verbatim. is_composite is
-- stored even though build_forecast_card only ever returns a card when it
-- is True: the snapshot must remain self-describing if that gate ever
-- changes (it is currently an honest stand-in for P311's uncalibrated
-- >=50% threshold).
CREATE TABLE forecast_card_snapshots (
    id BIGSERIAL PRIMARY KEY,
    object_region TEXT NOT NULL,
    is_composite BOOLEAN NOT NULL,
    signal_types JSONB NOT NULL,
    budget_estimate JSONB,
    evidence_chain JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX forecast_card_snapshots_region_idx ON forecast_card_snapshots (object_region);

-- Human-confirmed "this published tender is the one that forecast
-- predicted". Deliberately NOT auto-matched: no source document supplies a
-- forecast-to-tender identity algorithm, and the one identity helper that
-- exists (packages/tender/az_region_identity.py) canonicalizes only the
-- four regions actually observed in captured data, returning None
-- otherwise. Guessing the link would fabricate the very fact the P310
-- backtest is meant to measure. A human confirms it -- same ADR-0005
-- discipline the rest of this codebase applies wherever an algorithm would
-- have to be invented.
CREATE TABLE forecast_card_tender_links (
    id BIGSERIAL PRIMARY KEY,
    forecast_card_snapshot_id BIGINT NOT NULL REFERENCES forecast_card_snapshots (id),
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    note TEXT NOT NULL,
    confirmed_by TEXT NOT NULL,
    confirmed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (forecast_card_snapshot_id, tender_id)
);

CREATE INDEX forecast_card_tender_links_tender_idx ON forecast_card_tender_links (tender_id);
```

- [ ] **Step 6: Bump the expected schema version**

In `packages/platform/settings.py:24`, change the default from `"16"` to `"17"`:

```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "17")))
```

Note: tests no longer pass `expected_schema_version=` explicitly (PR #24 removed those overrides in favour of this single default), so this one edit is the whole bump. The single deliberate exception is `tests/integration/test_api_tender_health.py:37`'s `expected_schema_version=99`, which asserts readiness *fails* on a mismatch — leave it alone.

- [ ] **Step 7: Write the failing store test**

```python
# tests/integration/test_calibration_store.py
from datetime import UTC, datetime

import pytest

from packages.decision.calibration_model import LossReason, TenderOutcome
from packages.decision.calibration_store import (
    list_loss_reasons_by_outcome,
    list_overhead_buffer_contributions,
    load_tender_outcome,
    store_loss_reason,
    store_tender_outcome,
)
from packages.decision.execution_ledger_store import store_overhead_buffer_contribution

NOW = datetime(2026, 8, 11, tzinfo=UTC).isoformat()


def _outcome(tender_id: int, **overrides) -> TenderOutcome:
    base = dict(
        tender_id=tender_id,
        outcome="lost",
        our_submitted_amount="120000.00",
        winner_name="Rival LLC",
        winner_amount="98000.00",
        currency="AZN",
        announced_at=NOW,
        source_ref="public award notice seen by PM",
        entered_by="pm@unico.az",
        entered_at=NOW,
    )
    return TenderOutcome(**{**base, **overrides})


async def test_outcome_round_trips_with_amounts_intact(engine, seeded_tender_id):
    async with engine.begin() as conn:
        outcome_id = await store_tender_outcome(conn, _outcome(seeded_tender_id))
        loaded = await load_tender_outcome(conn, tender_id=seeded_tender_id)

    assert loaded is not None
    assert loaded["id"] == outcome_id
    assert loaded["outcome"] == "lost"
    # Decimal, not float -- money must not round-trip through binary float.
    assert str(loaded["our_submitted_amount"]) == "120000.00"
    assert str(loaded["winner_amount"]) == "98000.00"


async def test_missing_winner_amount_stays_none_and_is_not_coerced_to_zero(engine, seeded_tender_id):
    """Hard ban #3: a winner whose price the human does not know is
    'missing', which is a different fact from 'won for 0'."""
    async with engine.begin() as conn:
        await store_tender_outcome(conn, _outcome(seeded_tender_id, winner_amount=None))
        loaded = await load_tender_outcome(conn, tender_id=seeded_tender_id)

    assert loaded is not None
    assert loaded["winner_amount"] is None


async def test_load_returns_none_for_a_tender_with_no_recorded_outcome(engine, seeded_tender_id):
    async with engine.begin() as conn:
        assert await load_tender_outcome(conn, tender_id=seeded_tender_id) is None


async def test_second_outcome_for_one_tender_is_rejected_by_the_database(engine, seeded_tender_id):
    from sqlalchemy.exc import IntegrityError

    async with engine.begin() as conn:
        await store_tender_outcome(conn, _outcome(seeded_tender_id))

    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await store_tender_outcome(conn, _outcome(seeded_tender_id, outcome="won"))


async def test_multiple_loss_reasons_attach_to_one_outcome_in_insertion_order(engine, seeded_tender_id):
    async with engine.begin() as conn:
        outcome_id = await store_tender_outcome(conn, _outcome(seeded_tender_id))
        await store_loss_reason(
            conn,
            LossReason(loss_reason="dumping", note="30% under our cost", entered_by="pm", entered_at=NOW),
            tender_outcome_id=outcome_id,
        )
        await store_loss_reason(
            conn,
            LossReason(
                loss_reason="competitor_cheap_access",
                note="they own the quarry",
                entered_by="pm",
                entered_at=NOW,
            ),
            tender_outcome_id=outcome_id,
        )
        reasons = await list_loss_reasons_by_outcome(conn, tender_outcome_id=outcome_id)

    assert [r["loss_reason"] for r in reasons] == ["dumping", "competitor_cheap_access"]


async def test_overhead_buffer_contributions_are_readable(engine, seeded_tender_id):
    """Closes the write-only gap: nothing in the codebase ever SELECTed
    fact_count before this task."""
    async with engine.begin() as conn:
        await store_overhead_buffer_contribution(
            conn, tender_id=seeded_tender_id, deviation_category="downtime", fact_count=3, contributed_at=NOW
        )
        await store_overhead_buffer_contribution(
            conn, tender_id=seeded_tender_id, deviation_category="rework", fact_count=1, contributed_at=NOW
        )
        rows = await list_overhead_buffer_contributions(conn, tender_id=seeded_tender_id)

    assert {r["deviation_category"]: r["fact_count"] for r in rows} == {"downtime": 3, "rework": 1}
```

Add a `seeded_tender_id` fixture to `tests/integration/conftest.py` **only if one does not already exist** — first check for an existing tender-seeding fixture (`test_decision_api.py` has `tender_with_boq`) and reuse its approach rather than duplicating it. The fixture must insert a real `tenders` row (and the `tender_versions` row its FK chain needs) and return the id.

- [ ] **Step 8: Run it and confirm it fails**

Run: `python -m pytest tests/integration/test_calibration_store.py -q`
Expected: FAIL — `ModuleNotFoundError` for `calibration_store` (Docker must be running for testcontainers).

- [ ] **Step 9: Write the store**

```python
# packages/decision/calibration_store.py
"""Persistence for calibration-loop inputs (Phase 4, task 4.D,
TENDER_INTELLIGENCE_SPEC.md Section7.4, P319). tender_outcomes and
tender_loss_reasons are append-only (ADR-0003 layer 4 -- both are human
entries) -- no UPDATE/DELETE against either from this module.

list_overhead_buffer_contributions closes a real gap left by task 4.C:
overhead_buffer_contributions was write-only, with its only read being a
409 existence probe in the close-project route. Nothing had ever SELECTed
fact_count. This function reads the counts as they are -- it applies no
weighting, because no source supplies one (hard ban #2)."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .calibration_model import LossReason, TenderOutcome


def _ts(value: str | None) -> datetime | None:
    # asyncpg binds TIMESTAMPTZ by native datetime, not ISO string -- same
    # discipline as execution_ledger_store.py.
    return None if value is None else datetime.fromisoformat(value)


async def store_tender_outcome(conn: AsyncConnection, outcome: TenderOutcome) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO tender_outcomes
                    (tender_id, outcome, our_submitted_amount, winner_name, winner_amount,
                     currency, announced_at, source_ref, entered_by, entered_at)
                VALUES
                    (:tender_id, :outcome, :our_submitted_amount, :winner_name, :winner_amount,
                     :currency, :announced_at, :source_ref, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "tender_id": outcome.tender_id,
                "outcome": outcome.outcome,
                "our_submitted_amount": outcome.our_submitted_amount,
                "winner_name": outcome.winner_name,
                "winner_amount": outcome.winner_amount,
                "currency": outcome.currency,
                "announced_at": _ts(outcome.announced_at),
                "source_ref": outcome.source_ref,
                "entered_by": outcome.entered_by,
                "entered_at": _ts(outcome.entered_at),
            },
        )
    ).scalar_one()


async def load_tender_outcome(conn: AsyncConnection, *, tender_id: int) -> dict[str, Any] | None:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, outcome, our_submitted_amount, winner_name, winner_amount,
                           currency, announced_at, source_ref, entered_by, entered_at
                    FROM tender_outcomes WHERE tender_id = :tender_id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .first()
    )
    return None if row is None else dict(row)


async def store_loss_reason(conn: AsyncConnection, reason: LossReason, *, tender_outcome_id: int) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO tender_loss_reasons
                    (tender_outcome_id, loss_reason, note, entered_by, entered_at)
                VALUES (:tender_outcome_id, :loss_reason, :note, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "tender_outcome_id": tender_outcome_id,
                "loss_reason": reason.loss_reason,
                "note": reason.note,
                "entered_by": reason.entered_by,
                "entered_at": _ts(reason.entered_at),
            },
        )
    ).scalar_one()


async def list_loss_reasons_by_outcome(conn: AsyncConnection, *, tender_outcome_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_outcome_id, loss_reason, note, entered_by, entered_at
                    FROM tender_loss_reasons WHERE tender_outcome_id = :tender_outcome_id ORDER BY id
                    """
                ),
                {"tender_outcome_id": tender_outcome_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def list_overhead_buffer_contributions(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, deviation_category, fact_count, contributed_at
                    FROM overhead_buffer_contributions WHERE tender_id = :tender_id ORDER BY id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

- [ ] **Step 10: Run the store test and confirm it passes**

Run: `python -m pytest tests/integration/test_calibration_store.py -q`
Expected: PASS (6 tests)

- [ ] **Step 11: Run the full gate suite**

Run: `python -m pytest tests/ -q -m "not live_network"` then `python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py`
Expected: all pass. The schema bump means every migration-count/version assertion must agree on 17 — if any test still asserts 16, fix it here rather than leaving a mismatch.

- [ ] **Step 12: Commit**

```bash
git add migrations/0017_calibration_loop.sql packages/decision/calibration_model.py packages/decision/calibration_store.py packages/platform/settings.py tests/unit/test_calibration_model.py tests/integration/test_calibration_store.py
git commit -m "feat(decision): calibration-loop migration, outcome/loss-reason model and store (task 4.D), schema version 16->17"
```

---

### Task 2: Outcome and loss-reason API routes

**Files:**
- Create: `apps/api_tender/routers/calibration.py`
- Modify: `apps/api_tender/main.py`
- Test: `tests/integration/test_calibration_api.py`

**Interfaces:**
- Consumes: `TenderOutcome`, `LossReason`, `store_tender_outcome`, `load_tender_outcome`, `store_loss_reason`, `list_loss_reasons_by_outcome`, `list_overhead_buffer_contributions` (Task 1); `get_latest_decision_type` (`packages/decision/decision_store.py:209`).
- Produces: routes `POST /tenders/{tender_id}/outcome`, `POST /tenders/{tender_id}/outcome/loss-reasons`, `GET /tenders/{tender_id}/outcome`, `GET /tenders/{tender_id}/overhead-buffer`; permissions `decision.outcome.write`, `decision.outcome.read`.

**Behavioural requirements — all four must be tested, not just implemented:**

1. **Deny-by-default RBAC** on all four routes: no auth → 401; authenticated without the permission → 403. Both, per route type (`test_decision_api.py` is the precedent).
2. **An outcome requires the tender to have been decided** `bid`/`conditional_bid` — reuse `get_latest_decision_type`, 409 `tender_not_decided_bid`. A tender we never bid on has no outcome *for us*; recording one would pollute win/loss statistics with tenders we never entered. Mirror `execution_ledger.py:69`'s `_require_active_bid_decision` rather than reinventing the check.
3. **A duplicate outcome is 409**, not a second row (`tender_outcomes_tender_uniq` backs this; the route must check first and raise `ApiError`, so the caller gets the uniform envelope rather than a 500 from `IntegrityError`).
4. **Loss reasons are only accepted on a `lost` outcome** — 409 otherwise. A "why we lost" note on a won tender is a data-entry error, and silently storing it would corrupt the very rollup Task 4 builds.
5. **`write_audit_log`** on both mutations (`admin_users.py` and `execution_ledger.py:435` are the precedents — every mutation in this codebase audits).
6. **Validation is at the route boundary**, returning 422 — not left to the migration's `CHECK` to surface as a 500. This is the defect recorded as 4.C's sixth deferred item in `OPEN-QUESTIONS.md` (`capture_kind`/`mime_type`); do not repeat it here. Validate `outcome` against `OUTCOME_TYPES` and `loss_reason` against `LOSS_REASONS` explicitly, and let `TenderOutcome.__post_init__`'s `ValueError` map to 422 rather than propagating as a 500.

- [ ] **Step 1: Write the failing route tests**

```python
# tests/integration/test_calibration_api.py
# Fixtures (tender_app, client, pm_user, tender_with_boq) follow
# tests/integration/test_decision_api.py exactly -- read that file first and
# reuse its fixture bodies rather than writing new ones. This module needs no
# vendor app: none of these routes call the Vendor service.

CALIBRATION_PERMISSIONS = ("decision.outcome.write", "decision.outcome.read")


async def test_post_outcome_without_auth_is_401(client, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload())
    assert r.status_code == 401


async def test_post_outcome_authenticated_without_permission_is_403(client, user_without_permissions, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(user_without_permissions))
    assert r.status_code == 403


async def test_post_outcome_persists_and_audits(client, pm_user, decided_tender_id, engine):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert r.status_code == 200

    async with engine.begin() as conn:
        row = await load_tender_outcome(conn, tender_id=decided_tender_id)
        audit = (
            (await conn.execute(text("SELECT action FROM audit_log WHERE object_id = :oid"), {"oid": str(decided_tender_id)}))
            .scalars()
            .all()
        )

    assert row is not None and row["outcome"] == "lost"
    assert "calibration.record_outcome" in audit


async def test_outcome_on_a_tender_with_no_bid_decision_is_409(client, pm_user, undecided_tender_id):
    r = await client.post(f"/tenders/{undecided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "tender_not_decided_bid"


async def test_second_outcome_is_409_not_a_500_from_the_unique_index(client, pm_user, decided_tender_id):
    assert (
        await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    ).status_code == 200
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "outcome_already_recorded"


async def test_unknown_outcome_value_is_422_not_500(client, pm_user, decided_tender_id):
    """4.C's sixth deferred item was exactly this defect on another route --
    validation left to the migration CHECK, surfacing as 500. Not repeated."""
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(outcome="probably_lost"), headers=_auth(pm_user))
    assert r.status_code == 422


async def test_blank_source_ref_is_422_because_INV_15_requires_provenance(client, pm_user, decided_tender_id):
    r = await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(source_ref="  "), headers=_auth(pm_user))
    assert r.status_code == 422


async def test_loss_reason_on_a_won_outcome_is_409(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(outcome="won"), headers=_auth(pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "dumping", "note": "n"},
        headers=_auth(pm_user),
    )
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "outcome_not_a_loss"


async def test_other_loss_reason_without_a_note_is_422(client, pm_user, decided_tender_id):
    await client.post(f"/tenders/{decided_tender_id}/outcome", json=_payload(), headers=_auth(pm_user))
    r = await client.post(
        f"/tenders/{decided_tender_id}/outcome/loss-reasons",
        json={"loss_reason": "other", "note": "   "},
        headers=_auth(pm_user),
    )
    assert r.status_code == 422


async def test_get_overhead_buffer_returns_the_stored_counts(client, pm_user, decided_tender_id, engine):
    async with engine.begin() as conn:
        await store_overhead_buffer_contribution(
            conn, tender_id=decided_tender_id, deviation_category="downtime", fact_count=2, contributed_at=NOW
        )
    r = await client.get(f"/tenders/{decided_tender_id}/overhead-buffer", headers=_auth(pm_user))
    assert r.status_code == 200
    assert r.json()["items"][0]["fact_count"] == 2
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/integration/test_calibration_api.py -q`
Expected: FAIL — 404s on every route (router not registered).

- [ ] **Step 3: Write the router**

Write `apps/api_tender/routers/calibration.py` following `apps/api_tender/routers/execution_ledger.py`'s conventions exactly: `APIRouter(prefix="/tenders/{tender_id}", tags=["calibration"])`, pydantic request/response models, `Depends(get_connection)`, `require_permission(..., get_current_identity)` on every route, `ApiError` for every failure, `write_audit_log` after every successful mutation. Key implementation points:

```python
def _validated_outcome(payload: OutcomeRequest, *, tender_id: int, actor: str) -> TenderOutcome:
    """Route-boundary validation so a bad value is a clean 422, never a
    500 from the migration's CHECK constraint or from __post_init__
    escaping uncaught (4.C's sixth deferred item was exactly that defect
    on another route -- see docs/decisions/OPEN-QUESTIONS.md)."""
    try:
        return TenderOutcome(
            tender_id=tender_id,
            outcome=payload.outcome,
            our_submitted_amount=payload.our_submitted_amount,
            winner_name=payload.winner_name,
            winner_amount=payload.winner_amount,
            currency=payload.currency,
            announced_at=payload.announced_at,
            source_ref=payload.source_ref,
            entered_by=actor,
            entered_at=datetime.now(UTC).isoformat(),
        )
    except ValueError as exc:
        raise ApiError(status_code=422, code="invalid_outcome", message=str(exc)) from exc
```

For `POST /outcome`: call `_require_active_bid_decision` (import it from `execution_ledger.py` rather than duplicating the helper — it is already a module-level function there), then `load_tender_outcome`; if not `None`, raise `ApiError(409, "outcome_already_recorded", ...)`. For `POST /outcome/loss-reasons`: load the outcome; `None` → 404 `outcome_not_found`; `outcome != "lost"` → 409 `outcome_not_a_loss`; then build `LossReason` inside the same `try/except ValueError → 422` wrapper.

- [ ] **Step 4: Register the router**

In `apps/api_tender/main.py`, add the import and include it alongside the existing routers (follow how `execution_ledger` is registered — `build_app` from `packages/platform/app_factory.py` takes the routers the caller passes).

- [ ] **Step 5: Run the route tests and confirm they pass**

Run: `python -m pytest tests/integration/test_calibration_api.py -q`
Expected: PASS (11 tests)

- [ ] **Step 6: Run the full gate suite, then commit**

```bash
git add apps/api_tender/routers/calibration.py apps/api_tender/main.py tests/integration/test_calibration_api.py
git commit -m "feat(api-tender): tender outcome, loss post-mortem, and overhead-buffer read routes (task 4.D)"
```

---

### Task 3: Forecast card snapshots + human-confirmed tender link

**Files:**
- Create: `packages/tender/forecast_snapshot_store.py`
- Modify: `apps/api_tender/routers/calibration.py` (add a second, non-tender-prefixed router — follow `execution_ledger.py:455`'s `organization_router` precedent for a router whose path is not under `/tenders/{tender_id}`)
- Test: `tests/integration/test_forecast_snapshot_store.py`, and route tests appended to `tests/integration/test_calibration_api.py`

**Interfaces:**
- Consumes: `ForecastCard` (`packages/tender/forecast_card.py:56`), `build_object_region_forecast_card` (`packages/tender/signals_store.py:122`).
- Produces: `store_forecast_card_snapshot(conn, card, *, computed_at) -> int`, `load_forecast_card_snapshot(conn, *, snapshot_id) -> dict[str, Any] | None`, `confirm_forecast_tender_link(conn, *, snapshot_id, tender_id, note, confirmed_by, confirmed_at) -> int`, `list_links_by_snapshot(conn, *, snapshot_id) -> list[dict[str, Any]]`, `observed_lag_days(conn, *, snapshot_id, tender_id) -> int | None`.

**The lag measurement, precisely.** `observed_lag_days` returns whole days between the *earliest* `observed_at` in the snapshot's own `evidence_chain` and the linked tender's `tenders.created_at`. Two honesty requirements, both testable:

- The second operand is named **`first_observed_at`** in every response model and docstring, never "publication date". `tenders.created_at` is when *we first ingested* the tender, which is not when it was published — no captured eTender field supplies a real publication date. Labelling it otherwise would fabricate precision.
- It returns `None`, never `0` or a guess, when the evidence chain has no parseable `observed_at`. A missing lag is surfaced (hard ban #3).

It computes a *measured duration*, not a horizon, not a TTL, not a weight. Nothing consumes it to adjust anything — accumulating these measurements is exactly what `TBD-TIS-01`/`TBD-TIS-02` are blocked on.

- [ ] **Step 1: Write the failing store test**

```python
# tests/integration/test_forecast_snapshot_store.py
from datetime import UTC, datetime

from packages.tender.forecast_card import ForecastCard
from packages.tender.forecast_snapshot_store import (
    confirm_forecast_tender_link,
    list_links_by_snapshot,
    load_forecast_card_snapshot,
    observed_lag_days,
    store_forecast_card_snapshot,
)

NOW = datetime(2026, 8, 11, tzinfo=UTC).isoformat()


def _card(evidence_observed_at: str = "2026-02-01T00:00:00+00:00") -> ForecastCard:
    return ForecastCard(
        object_region="ZAQATALA",
        is_composite=True,
        signal_types=frozenset({"donor_pipeline_project", "design_tender"}),
        budget_estimate={"source": "donor_pipeline_project", "total_amount_usd_text": "12,000,000"},
        evidence_chain=(
            {
                "signal_type": "donor_pipeline_project",
                "source": "worldbank",
                "observed_at": evidence_observed_at,
                "raw_snapshot_id": 1,
                "value": {},
            },
        ),
    )


async def test_snapshot_round_trips_every_forecast_card_field(engine):
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, _card(), computed_at=NOW)
        loaded = await load_forecast_card_snapshot(conn, snapshot_id=snapshot_id)

    assert loaded is not None
    assert loaded["object_region"] == "ZAQATALA"
    assert loaded["is_composite"] is True
    assert sorted(loaded["signal_types"]) == ["design_tender", "donor_pipeline_project"]
    assert loaded["budget_estimate"]["total_amount_usd_text"] == "12,000,000"
    assert len(loaded["evidence_chain"]) == 1


async def test_human_confirmed_link_is_recorded_with_its_author(engine, seeded_tender_id):
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, _card(), computed_at=NOW)
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="same road section, same buyer",
            confirmed_by="pm@unico.az",
            confirmed_at=NOW,
        )
        links = await list_links_by_snapshot(conn, snapshot_id=snapshot_id)

    assert len(links) == 1
    assert links[0]["confirmed_by"] == "pm@unico.az"
    assert links[0]["tender_id"] == seeded_tender_id


async def test_duplicate_link_is_rejected_by_the_unique_constraint(engine, seeded_tender_id):
    from sqlalchemy.exc import IntegrityError

    import pytest

    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, _card(), computed_at=NOW)
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="n",
            confirmed_by="pm",
            confirmed_at=NOW,
        )

    with pytest.raises(IntegrityError):
        async with engine.begin() as conn:
            await confirm_forecast_tender_link(
                conn,
                snapshot_id=snapshot_id,
                tender_id=seeded_tender_id,
                note="n",
                confirmed_by="pm",
                confirmed_at=NOW,
            )


async def test_observed_lag_is_measured_from_earliest_evidence_to_first_observed_at(engine, seeded_tender_id):
    """The measurement TBD-TIS-01/TBD-TIS-02 are blocked on. Nothing
    consumes it to adjust anything -- it is recorded, not applied."""
    async with engine.begin() as conn:
        # seeded_tender_id's tenders.created_at is set by the fixture; the
        # fixture must pin it explicitly so this assertion is deterministic.
        snapshot_id = await store_forecast_card_snapshot(
            conn, _card(evidence_observed_at="2026-02-01T00:00:00+00:00"), computed_at=NOW
        )
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="n",
            confirmed_by="pm",
            confirmed_at=NOW,
        )
        lag = await observed_lag_days(conn, snapshot_id=snapshot_id, tender_id=seeded_tender_id)

    assert lag == 191  # 2026-02-01 -> 2026-08-11, pinned by the fixture


async def test_lag_is_none_when_no_evidence_carries_a_parseable_observed_at(engine, seeded_tender_id):
    """Hard ban #3: an unmeasurable lag is surfaced as missing, not 0."""
    card = ForecastCard(
        object_region="LERIK",
        is_composite=True,
        signal_types=frozenset({"design_tender", "procurement_plan"}),
        budget_estimate=None,
        evidence_chain=(
            {"signal_type": "design_tender", "source": "etender", "observed_at": None, "raw_snapshot_id": 2, "value": {}},
        ),
    )
    async with engine.begin() as conn:
        snapshot_id = await store_forecast_card_snapshot(conn, card, computed_at=NOW)
        await confirm_forecast_tender_link(
            conn,
            snapshot_id=snapshot_id,
            tender_id=seeded_tender_id,
            note="n",
            confirmed_by="pm",
            confirmed_at=NOW,
        )
        assert await observed_lag_days(conn, snapshot_id=snapshot_id, tender_id=seeded_tender_id) is None
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/integration/test_forecast_snapshot_store.py -q`
Expected: FAIL — `ModuleNotFoundError` for `forecast_snapshot_store`.

- [ ] **Step 3: Implement the store**

Write `packages/tender/forecast_snapshot_store.py`. `signal_types` is a `frozenset` on the dataclass and JSONB in the column — serialize as a **sorted list** so the stored JSON is deterministic (`json.dumps(sorted(card.signal_types))`), and note that in a comment. Follow `packages/tender/signals_store.py` for how this codebase binds JSONB parameters. `observed_lag_days` reads the snapshot's `evidence_chain`, collects every parseable `observed_at`, and returns `None` if none parse; otherwise `(tenders.created_at - min(observed_at)).days`.

- [ ] **Step 4: Run the store test and confirm it passes**

Run: `python -m pytest tests/integration/test_forecast_snapshot_store.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Add the routes**

Add to `apps/api_tender/routers/calibration.py` a second router (not prefixed by `/tenders/{tender_id}`): `POST /forecast-snapshots` (persist the card currently computed for a region — build it via `build_object_region_forecast_card`, and return 409 `no_forecast_card` when it returns `None`, since below the `is_composite` bar there is genuinely no card to snapshot), `POST /forecast-snapshots/{snapshot_id}/tender-link`, `GET /forecast-snapshots/{snapshot_id}` (including `links` with each link's `observed_lag_days` and `first_observed_at`). Permissions `tender.forecast_snapshot.write` / `.read`. Audit both mutations. Add route tests for 401/403 on each, the 409 below-threshold case, and one happy path asserting `observed_lag_days` appears in the response.

- [ ] **Step 6: Run the full gate suite, then commit**

```bash
git add packages/tender/forecast_snapshot_store.py apps/api_tender/routers/calibration.py tests/integration/test_forecast_snapshot_store.py tests/integration/test_calibration_api.py
git commit -m "feat(tender,api-tender): persist forecast cards with human-confirmed tender links and measured lag (task 4.D)"
```

---

### Task 4: Calibration comparison — winner price vs our SCG-derived cost, with coverage

**Files:**
- Create: `packages/decision/calibration_summary.py`
- Modify: `apps/api_tender/routers/calibration.py`
- Test: `tests/unit/test_calibration_summary.py`, plus route tests appended to `tests/integration/test_calibration_api.py`

**Interfaces:**
- Consumes: `load_tender_outcome`, `list_loss_reasons_by_outcome` (Task 1); `BoqMatchSummary`/`summarize_boq_matches` (`packages/decision/boq_summary.py:28,41`); `rank_executable_candidates_by_tco` (`packages/decision/matching.py:209`).
- Produces: `PriceComparison` dataclass and `compare_winner_to_our_basis(...) -> PriceComparison`; `summarize_loss_reasons(rows) -> dict[str, int]`.

**Why this comparison is honest, and the one trap to avoid.** Spec §7.4 wants *"цена победителя vs своя оценка рыночной себестоимости → где база SCG врёт"*. Both operands are now real: the winner's price is human-entered (Task 1), and an SCG-derived cost basis is computable from existing data — `rank_executable_candidates_by_tco` already produces a TCO per BOQ line from real offers. **No formula is invented; this is arithmetic over data already present.**

The trap: BOQ coverage is partial by design (`bid_readiness.py`'s ~85% threshold exists precisely because it never reaches 100%). Comparing a *partial* cost sum against a *whole-tender* winner price would produce a number that looks like a margin and is actually an artifact of missing coverage. So `PriceComparison` must **always** carry the coverage it was computed over, and must never expose a bare ratio without it. That is hard ban #3 applied to arithmetic: the incompleteness travels with the number.

Deliberately NOT produced here: any verdict about *which* of §7.4's three diagnoses applies (`дыра в вендорах` / `демпинг` / `«нарисованный» тендер`). The spec says these are "разные выводы" from the same delta but supplies no rule for choosing between them — a human reads the delta plus the loss reasons they recorded and concludes. Emitting a verdict would be an invented classifier.

- [ ] **Step 1: Write the failing summary test**

```python
# tests/unit/test_calibration_summary.py
from decimal import Decimal

from packages.decision.calibration_summary import compare_winner_to_our_basis, summarize_loss_reasons


def test_comparison_carries_the_coverage_it_was_computed_over():
    c = compare_winner_to_our_basis(
        winner_amount=Decimal("98000"),
        our_submitted_amount=Decimal("120000"),
        our_scg_cost_basis=Decimal("90000"),
        priced_line_count=17,
        total_line_count=20,
    )
    assert c.winner_vs_our_submitted == Decimal("-22000")
    assert c.winner_vs_our_cost_basis == Decimal("8000")
    assert c.coverage_line_count == 17
    assert c.total_line_count == 20
    assert c.is_partial_coverage is True


def test_full_coverage_is_flagged_as_not_partial():
    c = compare_winner_to_our_basis(
        winner_amount=Decimal("1"),
        our_submitted_amount=Decimal("1"),
        our_scg_cost_basis=Decimal("1"),
        priced_line_count=5,
        total_line_count=5,
    )
    assert c.is_partial_coverage is False


def test_a_missing_winner_amount_yields_none_deltas_not_zero():
    """Hard ban #3: unknown is not zero. A winner whose price we do not
    know must not read as 'they bid nothing'."""
    c = compare_winner_to_our_basis(
        winner_amount=None,
        our_submitted_amount=Decimal("120000"),
        our_scg_cost_basis=Decimal("90000"),
        priced_line_count=17,
        total_line_count=20,
    )
    assert c.winner_vs_our_submitted is None
    assert c.winner_vs_our_cost_basis is None
    # The operand we DO have is still reported -- a missing operand does not
    # blank the whole comparison.
    assert c.our_submitted_amount == Decimal("120000")


def test_no_ratio_is_exposed_without_coverage_travelling_with_it():
    c = compare_winner_to_our_basis(
        winner_amount=Decimal("98000"),
        our_submitted_amount=Decimal("120000"),
        our_scg_cost_basis=Decimal("90000"),
        priced_line_count=1,
        total_line_count=20,
    )
    # 1 of 20 lines priced: the delta exists but must be marked partial so
    # no caller can read it as a whole-tender margin.
    assert c.is_partial_coverage is True


def test_loss_reason_rollup_counts_each_category():
    rows = [{"loss_reason": "dumping"}, {"loss_reason": "dumping"}, {"loss_reason": "drawn_tender"}]
    assert summarize_loss_reasons(rows) == {"dumping": 2, "drawn_tender": 1}


def test_loss_reason_rollup_of_nothing_is_empty_not_a_zero_filled_shape():
    assert summarize_loss_reasons([]) == {}
```

- [ ] **Step 2: Run and confirm failure**

Run: `python -m pytest tests/unit/test_calibration_summary.py -q`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Implement `calibration_summary.py`**

Pure module, no DB, no network (same shape as `execution_ledger_summary.py`). `PriceComparison` is a frozen dataclass carrying `winner_amount`, `our_submitted_amount`, `our_scg_cost_basis`, `winner_vs_our_submitted`, `winner_vs_our_cost_basis`, `coverage_line_count`, `total_line_count`, `is_partial_coverage`. Every delta is `None` when either operand is `None`. Use `Decimal` throughout — never `float` for money.

- [ ] **Step 4: Run the summary test and confirm it passes**

Run: `python -m pytest tests/unit/test_calibration_summary.py -q`
Expected: PASS (6 tests)

- [ ] **Step 5: Add `GET /tenders/{tender_id}/calibration`**

Returns the outcome, its loss reasons and their rollup, the `PriceComparison`, and the overhead-buffer counts. The SCG cost basis comes from the same path `GET /bid-readiness-candidate` already uses (`list_boq_lines_by_event` → `list_vendor_offers` → `match_boq_line`); reuse that code rather than duplicating it. Return 404 `outcome_not_found` when no outcome is recorded — a calibration view with no outcome is meaningless, and inventing an empty one would imply a fact. Permission `decision.outcome.read`.

Add route tests: 401, 403, 404-with-no-outcome, and a happy path asserting both that the deltas are present and that `is_partial_coverage` is reported.

- [ ] **Step 6: Run the full gate suite, then commit**

```bash
git add packages/decision/calibration_summary.py apps/api_tender/routers/calibration.py tests/unit/test_calibration_summary.py tests/integration/test_calibration_api.py
git commit -m "feat(decision,api-tender): winner-vs-our-basis price comparison with mandatory coverage, loss-reason rollup (task 4.D)"
```

---

### Task 5: Buyer rollup, close-out docs, and the deferred-items record

**Files:**
- Modify: `packages/decision/calibration_store.py`, `apps/api_tender/routers/calibration.py`, `docs/reports/WORKLOG.md`, `docs/decisions/OPEN-QUESTIONS.md`
- Test: `tests/integration/test_calibration_api.py`

**Interfaces:**
- Consumes: everything from Tasks 1–4.
- Produces: `list_outcomes_by_organization_voen(conn, *, organization_voen) -> list[dict[str, Any]]`; route `GET /organizations/{organization_voen}/outcomes`.

- [ ] **Step 1: Write the failing buyer-rollup test**

Follow `list_execution_facts_by_organization_voen` (`packages/decision/calibration_store.py`'s sibling in `execution_ledger_store.py:98`) for the `organization_voen` join through `tender_versions`' latest row — reuse that exact join shape rather than writing a new one. Test that two tenders sharing one buyer's VÖEN both appear, that a third tender under a different VÖEN does not, and that each row carries its loss reasons.

- [ ] **Step 2: Implement the store function and the route**

Route goes on the existing non-tender-prefixed router (Task 3), permission `decision.outcome.read`, with 401/403 tests.

- [ ] **Step 3: Run the full gate suite**

Run all five gates. Every one must pass before the docs step.

- [ ] **Step 4: Write the WORKLOG entry**

Append to `docs/reports/WORKLOG.md` (append only — never rewrite): what was built, the real test-run output pasted verbatim, and — most importantly — an explicit statement that **§7.4's actual calibration was NOT built and why**, using the table from this plan's "Why this scope" section. A reader must not come away thinking P319 is satisfied.

- [ ] **Step 5: Record every deferred item in OPEN-QUESTIONS.md**

One entry, dated, covering at minimum:
1. `TBD-TIS-02` (signal weights, confidence tiers) — unchanged; now has a *path* to resolution (persisted snapshots + confirmed links + measured lag) but no data volume yet.
2. `TBD-TIS-01` (numeric TTL per fact class) — unchanged, same reason.
3. The overhead-buffer **cost overlay** — still unbuilt; this task made the counts readable, not weighted. No source supplies the weighting.
4. `cancelled` on `OUTCOME_TYPES` and `other` on `LOSS_REASONS` — this task's own additions, with the reasoning from Task 1 (preventing a forced miscategorisation, which would corrupt the loss analysis).
5. `tenders.created_at` used as `first_observed_at` — it is *not* a publication date; no captured eTender field supplies one, so measured lag is "signal → we first saw the tender", which is a lower bound on the real horizon. Anyone calibrating horizons later must know this.
6. No eTender award/result connector — the `EventStatus` award value is still undecoded and the public list resource carries no monetary field, so outcomes are human-entered by design, not by oversight. Resolving this needs a real network capture session (same discipline as the Q&A gap).
7. No verdict is emitted about which of §7.4's three diagnoses explains a given delta — no rule exists to choose between them.
8. Whether Phase 4's exit gate can close with the loop *recording* but not yet *calibrating* — an owner call, since P319's own wording ("after N closed cycles… statistically more accurate") is untestable until N cycles exist.

- [ ] **Step 6: Commit**

```bash
git add packages/decision/calibration_store.py apps/api_tender/routers/calibration.py tests/integration/test_calibration_api.py docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "feat(decision,api-tender): buyer outcome rollup; docs(worklog,open-questions): task 4.D close-out"
```

---

## Self-Review

**Spec coverage.** §7.4's four bullets map as follows: winner-vs-our-estimate → Tasks 1, 2, 4 (both operands now exist; the comparison is arithmetic with mandatory coverage). Loss post-mortem → Tasks 1, 2, 5 (typed with the spec's own three categories plus an honest `other`, rolled up per buyer). Per-buyer horizon recalibration → Task 3 builds the **measurement** only; the recalibration itself is blocked on `TBD-TIS-01`/`TBD-TIS-02` and is recorded, not built. Overhead buffer overlay → Task 1/2 make it **readable**; the overlay formula has no source and is recorded as still-open. P319 itself is explicitly **not** claimed as satisfied — Task 5, Step 4 requires the WORKLOG to say so plainly.

**Placeholder scan.** No `TBD`/`TODO`/"implement later"/"add appropriate error handling" remains. The literal strings `TBD-TIS-01`/`TBD-TIS-02`/`D-VND-REP` appear only as *references to real tracked decision IDs* — that is required by `AGENTS.md` hard ban #2, not a placeholder. Tasks 3–5 point at existing files to copy conventions from (`signals_store.py`, `execution_ledger_store.py:98`, `execution_ledger.py:455`) rather than restating code that already exists in the repo; that is deliberate reuse, and each cites an exact path and line.

**Type consistency.** `TenderOutcome`/`LossReason` field names are identical in the model (Task 1 Step 3), the store binds (Task 1 Step 9), and the route builder (Task 2 Step 3). `store_forecast_card_snapshot`/`confirm_forecast_tender_link`/`observed_lag_days` keep the same signatures in Task 3's Interfaces block, its tests, and Task 4's consumption. `list_overhead_buffer_contributions` is defined in Task 1 and consumed in Tasks 2 and 4 under the same name. Money is `Decimal` or `str` end to end — never `float`.

**One scope note for the reviewer.** Task 3 (forecast-card persistence) is separable: it serves Phase 2's still-open P310 backtest as much as 4.D's horizon calibration. It is included because per-buyer horizons cannot be measured at all without it, but if the owner prefers a tighter 4.D, Task 3 can be lifted into its own plan without affecting Tasks 1, 2, 4, or 5.
