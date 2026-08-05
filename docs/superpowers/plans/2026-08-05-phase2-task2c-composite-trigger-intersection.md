# Phase 2, Task 2.C — Composite-trigger intersection detection — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real, non-fabricated core of `TENDER_INTELLIGENCE_SPEC.md` §5.3's forecast
engine — detecting that an object has accumulated signals from **two or more independent
`signal_type`s**, which is P310's own definition of a genuine forecast trigger ("пересечение
независимых сигналов по одному объекту, не одиночный сигнал" — intersection of independent signals
on one object, not a single signal) — and prove it against the one real case that exists today
(Zaqatala rayon: `design_tender` + `procurement_plan`) plus a real negative case (Siyəzən rayon:
`design_tender` only).

**Architecture:** A pure classifier (`packages/tender/object_intersection.py`, no DB/network, same
shape as `signal_model.py`/`boq_line_model.py`) takes the rows `signals_store.py` already knows how
to fetch (`list_signals_by_object_region`) and reports the distinct `signal_type`s present plus a
literal boolean `is_composite` (`len(signal_types) >= 2`). A thin async wrapper in `signals_store.py`
composes the two. Deliberately **not** built: §5.3's weak/medium/strong confidence tiers and
TTL-based decay/"frozen" state — both require numbers (`TBD-TIS-02` tier thresholds, `TBD-TIS-01` TTL
durations) that `AGENTS.md` hard ban #2 forbids inventing; both are recorded as open in
`docs/decisions/OPEN-QUESTIONS.md` instead.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, pytest + pytest-asyncio, testcontainers Postgres
(via `tests/integration/conftest.py`'s `engine` fixture) — no new dependencies, no schema migration
(reuses the existing `signals` table and `list_signals_by_object_region` query).

## Global Constraints

- **Never invent a number for a `TBD-nn` placeholder** (`AGENTS.md`/`CLAUDE.md` hard ban #2). §5.3's
  ~30%/60%/85% confidence tiers are explicitly "an illustration of the model's shape, not calibrated
  thresholds" per the spec's own text — real percentages are `TBD-TIS-02`, pending the P310 backtest.
  TTL expiry durations are `TBD-TIS-01`. Neither may be coded as a real number in this task; both stay
  the literal strings `TBD-TIS-01`/`TBD-TIS-02` wherever mentioned in docs.
- **No new external fetch needed.** Both proof cases (Zaqatala composite, Siyəzən non-composite) are
  provable entirely from fixtures already frozen in `fixtures/tender-snapshots/etender/`
  (`design_tender_search_page1.raw.json`, `app_list_zaqatala_2026.raw.json`) — do not add a live-fetch
  test for this task.
- **Object identity stays region-scoped.** `object_customer`/`object_project_type` canonicalization is
  future work, not in scope here — every function in this plan operates on `object_region` only,
  matching `list_signals_by_object_region`'s existing scope.
- Every requirement ID used (`INV-15`, `P310`, `TBD-TIS-01`, `TBD-TIS-02`) must trace to
  `TENDER_INTELLIGENCE_SPEC.md` §5.3 or `migrations/0008_signals.sql`'s existing comments — do not
  invent a new requirement ID.

---

## Task 1: `object_intersection.py` — pure intersection-detection primitive

**Files:**
- Create: `packages/tender/object_intersection.py`
- Test: `tests/unit/test_object_intersection.py`

**Interfaces:**
- Produces: `@dataclass(frozen=True) class ObjectIntersection` with fields `object_region: str`,
  `signal_types: frozenset[str]`, `is_composite: bool`; and
  `detect_intersection(object_region: str, signal_rows: Sequence[dict[str, Any]]) -> ObjectIntersection`
  — pure function, reads only each row's `"signal_type"` key, no DB, no network.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the pure intersection-detection primitive (TENDER_INTELLIGENCE_SPEC.md
§5.3, P310)."""

from packages.tender.object_intersection import detect_intersection


def test_single_signal_type_is_not_composite():
    result = detect_intersection("Siyəzən", [{"signal_type": "design_tender"}])
    assert result.object_region == "Siyəzən"
    assert result.signal_types == frozenset({"design_tender"})
    assert result.is_composite is False


def test_two_distinct_signal_types_is_composite():
    result = detect_intersection(
        "Zaqatala",
        [
            {"signal_type": "design_tender"},
            {"signal_type": "design_tender"},
            {"signal_type": "procurement_plan"},
        ],
    )
    assert result.signal_types == frozenset({"design_tender", "procurement_plan"})
    assert result.is_composite is True


def test_no_signals_is_not_composite():
    result = detect_intersection("Naxçıvan", [])
    assert result.signal_types == frozenset()
    assert result.is_composite is False
```

Save as `tests/unit/test_object_intersection.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_object_intersection.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.object_intersection'`.

- [ ] **Step 3: Write `object_intersection.py`**

```python
"""Composite-trigger intersection primitive (TENDER_INTELLIGENCE_SPEC.md
§5.3, P310). Pure assembly, no DB, no network -- same shape as
signal_model.py/boq_line_model.py.

P310's own definition of a real forecast trigger is exactly this:
"пересечение независимых сигналов по одному объекту, не одиночный сигнал"
(intersection of independent signals on one object, not a single signal).
`is_composite` is that literal boolean fact -- has this object accumulated
signals from 2+ distinct signal_types -- and nothing more.

Deliberately NOT implemented here (both blocked by AGENTS.md hard ban #2 --
never invent a number for a TBD-nn placeholder):
- Section 5.3's weak/medium/strong confidence tiers. The spec's own text is
  explicit that the illustrative ~30%/60%/85% figures are "a shape of the
  model, not calibrated thresholds" -- the real numbers are TBD-TIS-02,
  pending the P310 backtest (>=30 already-published tenders). The tier
  compositions the spec names (e.g. weak = "program line + strategy
  mention") also reference signal categories (decrees, budgets) this
  project has no source for yet, so there is no honest mapping from
  signal_type count to a named tier today.
- TTL-based decay / "frozen" object state. `ttl_class` on a Signal is a
  label only (see signal_model.py) -- actual expiry durations are
  TBD-TIS-01. Without a duration, "is this chain broken" can't be computed
  without inventing one.

Both are recorded as open in docs/decisions/OPEN-QUESTIONS.md rather than
faked with placeholder numbers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObjectIntersection:
    object_region: str
    signal_types: frozenset[str]
    is_composite: bool


def detect_intersection(object_region: str, signal_rows: Sequence[dict[str, Any]]) -> ObjectIntersection:
    signal_types = frozenset(row["signal_type"] for row in signal_rows)
    return ObjectIntersection(
        object_region=object_region,
        signal_types=signal_types,
        is_composite=len(signal_types) >= 2,
    )
```

Save as `packages/tender/object_intersection.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_object_intersection.py -v`
Expected: all three PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/object_intersection.py tests/unit/test_object_intersection.py
git commit -m "feat(tender): pure composite-trigger intersection primitive (P310)"
```

---

## Task 2: `signals_store.detect_object_region_intersection` — real proof on Zaqatala + Siyəzən

**Files:**
- Modify: `packages/tender/signals_store.py`
- Test: `tests/integration/test_object_region_intersection_store.py`

**Interfaces:**
- Consumes: `list_signals_by_object_region` (existing), `detect_intersection`/`ObjectIntersection`
  (Task 1).
- Produces:
  `async def detect_object_region_intersection(conn: AsyncConnection, *, object_region: str) -> ObjectIntersection`.

- [ ] **Step 1: Write the failing test (real fixtures, no live fetch)**

```python
"""Real proof that `detect_object_region_intersection` correctly classifies a genuine
composite object (Zaqatala: design_tender + procurement_plan) against a genuine
non-composite one (Siyəzən: design_tender only) -- both cases from data already frozen
as fixtures, no new live fetch needed."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page, ingest_procurement_plan_page
from packages.tender.signals_store import detect_object_region_intersection

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"

DESIGN_QUERY_PARAMS = {
    "EventType": "",
    "PageSize": 10,
    "EventStatus": 1,
    "Keyword": "layihə",
    "buyerOrganizationName": "",
    "documentNumber": "",
    "publishDateFrom": "",
    "publishDateTo": "",
    "AwardedparticipantName": "",
    "AwardedparticipantVoen": "",
    "DocumentViewType": "",
    "IsArchived": False,
}


async def test_zaqatala_is_a_real_composite_intersection(engine):
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)
    app_raw = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    app_payload = json.loads(app_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_QUERY_PARAMS,
            correlation_id="corr-intersection-composite-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        await ingest_procurement_plan_page(
            conn,
            raw_body=app_raw,
            payload=app_payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-intersection-composite-2",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        result = await detect_object_region_intersection(conn, object_region="Zaqatala")
        assert result.object_region == "Zaqatala"
        assert result.signal_types == frozenset({"design_tender", "procurement_plan"})
        assert result.is_composite is True


async def test_siyezen_is_a_real_non_composite_object(engine):
    # Real fact: page1's only Siyəzən tender (event 356386) has no matching
    # procurement-plan fixture -- exactly one signal_type, the honest
    # negative case for P310's "intersection, not a single signal" bar.
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_QUERY_PARAMS,
            correlation_id="corr-intersection-single-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        result = await detect_object_region_intersection(conn, object_region="Siyəzən")
        assert result.signal_types == frozenset({"design_tender"})
        assert result.is_composite is False
```

Save as `tests/integration/test_object_region_intersection_store.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_object_region_intersection_store.py -v` (Docker must be running)
Expected: FAIL with `ImportError: cannot import name 'detect_object_region_intersection'`.

- [ ] **Step 3: Add `detect_object_region_intersection` to `signals_store.py`**

Read `packages/tender/signals_store.py` first. Add this import alongside the existing
`from .signal_model import Signal` line:

```python
from .object_intersection import ObjectIntersection, detect_intersection
```

Append this function at the end of the file (after `list_signals_by_object_region`):

```python
async def detect_object_region_intersection(conn: AsyncConnection, *, object_region: str) -> ObjectIntersection:
    """TENDER_INTELLIGENCE_SPEC.md §5.3 / P310's own definition of a real
    forecast trigger -- an intersection of independent signal_types on one
    object, not a single signal. Composes list_signals_by_object_region's
    real accumulated rows with object_intersection.py's pure classifier;
    does not itself assign a weak/medium/strong tier or apply TTL decay --
    both remain blocked on TBD-TIS-02/TBD-TIS-01 (see OPEN-QUESTIONS.md)."""
    rows = await list_signals_by_object_region(conn, object_region=object_region)
    return detect_intersection(object_region, rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_object_region_intersection_store.py -v`
Expected: both PASS.

- [ ] **Step 5: Re-run the full unit + integration suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`
Expected: all previously-passing tests still pass, plus the 3 new unit + 2 new integration tests.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/signals_store.py tests/integration/test_object_region_intersection_store.py
git commit -m "feat(tender): real composite-trigger proof on Zaqatala vs Siyezen (P310)"
```

---

## Task 3: WORKLOG, Open Questions, full gate, final commit

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

Append to `docs/reports/WORKLOG.md`, matching the existing entries' style (see the two most recent
2026-08-05 entries for exact tone/section headers: `**Сделано:**`, `**Вывод полного прогона
(Fast+Full gate):**`, `**Дальше:**`, `**Блокеры:**`). Content to include, plainly:

- This plan built the real, non-fabricated core of the §5.3 forecast engine: `is_composite` is P310's
  own literal definition (2+ distinct `signal_type`s on one object), proven against the real Zaqatala
  case (`design_tender` + `procurement_plan`, both real, already-ingested fixtures) and a real negative
  case (Siyəzən: `design_tender` only, no matching procurement-plan fixture exists).
- What was deliberately NOT built and why: §5.3's weak/medium/strong confidence tiers (blocked on
  `TBD-TIS-02` — the spec's own text calls its illustrative percentages "a shape of the model, not
  calibrated thresholds", pending the P310 backtest on ≥30 already-published tenders) and TTL-based
  decay/"frozen" object state (blocked on `TBD-TIS-01`, since `ttl_class` is a label only, no duration
  exists to compute expiry against). Building either now would mean inventing a number for a `TBD-nn`
  placeholder, which `AGENTS.md` hard ban #2 forbids.
- Only one real overlapping object exists so far (Zaqatala) — the intersection primitive is proven
  correct, but its real-world coverage is still exactly as thin as task 2.B left it. Widening
  procurement-plan/design-tender coverage (more regions, more years) remains open, not attempted here.
- Files: `packages/tender/object_intersection.py` (new), `packages/tender/signals_store.py` (modified),
  `tests/unit/test_object_intersection.py` (new, 3), `tests/integration/test_object_region_intersection_store.py`
  (new, 2).
- Paste the actual `pytest`/`ruff`/`mypy`/`check_v1_untouched.py` output from Step 1 into the
  `**Вывод полного прогона (Fast+Full gate):**` code block — do not fabricate pass counts.

- [ ] **Step 3: Open Questions entry**

Append to `docs/decisions/OPEN-QUESTIONS.md`, same format as existing entries (`**Context:**`,
`**Deviation/assumption:**`, `**Consequence that must not be silently dropped:**`, `**Owner follow-up
needed:**`). Content:

- Context: task 2.C's composite-trigger engine (`TENDER_INTELLIGENCE_SPEC.md` §5.3) needs
  weak/medium/strong confidence tiers and TTL-based decay to be the "forecast" the spec describes;
  this task built only the literal intersection-detection fact (`is_composite`), not the tiers or decay.
- Deviation/assumption: tiers and decay are left unimplemented rather than approximated, because both
  require inventing a number for `TBD-TIS-01` (TTL durations) / `TBD-TIS-02` (tier thresholds), which
  `AGENTS.md` hard ban #2 forbids. No source document supplies real numbers for either yet.
- Consequence: `detect_object_region_intersection` currently reports only a boolean
  (`is_composite`) and the raw set of converged `signal_type`s — it cannot yet say *how confident* a
  forecast is, or whether an old chain should be considered "frozen". Any UI/delivery work (§5.4, task
  2.D) that expects a probability or a freshness state will find neither here.
- Owner follow-up needed: yes, non-blocking. `TBD-TIS-01`/`TBD-TIS-02` need the owner's
  research/approval gate (real TTL durations per `ttl_class`, and the P310 backtest against ≥30
  already-published tenders) before tiers or decay can be built for real, per PRD §5.7.4/§13's existing
  TBD-resolution process.

- [ ] **Step 4: Commit**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(tender): record composite-trigger intersection proof, tier/TTL still TBD-TIS-01/02"
```

---

## Self-review notes

- **Spec coverage:** §5.3's own definition of a forecast trigger ("intersection of independent
  signals on one object, not a single signal") is directly implemented and proven with real data
  (Task 1 + Task 2). The tier/TTL portions of §5.3 are explicitly out of scope, matching the spec's own
  caveat that those numbers are illustrative only — recorded as open, not silently skipped (Task 3).
- **No placeholders:** every test case uses fixtures already committed to the repo
  (`design_tender_search_page1.raw.json`, `app_list_zaqatala_2026.raw.json`) and real, previously-proven
  ingestion functions (`ingest_design_tender_signals_page`, `ingest_procurement_plan_page`) — no new
  network calls, no synthetic data standing in for a real case.
- **Type consistency:** `ObjectIntersection`/`detect_intersection` (Task 1) are consumed unchanged by
  `detect_object_region_intersection` (Task 2) with the same field names (`object_region`,
  `signal_types`, `is_composite`) used throughout.
