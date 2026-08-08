# Phase 4, Task 4.A — Decision Core (Go/No-Go → Bid) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Implement `TENDER_INTELLIGENCE_SPEC.md` §7.1's Decision Core: an append-only, human-authored `Decision` record (Go/No-Go, then Bid/No-Bid/Conditional Bid) backed by the one real derived signal the system can compute today (BOQ money coverage + single-vendor-critical lines, from the already-built `packages/decision/matching.py`/`boq_summary.py`), plus INV-20's lock-in flagging for critical lines on a Bid decision.

**Architecture:** `packages/decision` gains its first persisted domain model. A new `apps/api_tender/routers/decision.py` router lives on the Tender service (not Vendor — ADR-0006 only splits the tender↔vendor seam; `packages/decision` already imports `packages/tender`'s `BoqLine` in-process and reaches Vendor data only through `packages/contracts`, unchanged from task 3.D). The GET bid-readiness endpoint is the first place in the whole codebase that actually calls `match_boq_line`/`summarize_boq_matches` against a real, persisted tender's BOQ lines and a real (paginated) vendor-offer fetch — closing a gap task 3.D's final review flagged as real but deferred.

**Tech Stack:** Python 3.12, FastAPI, httpx, SQLAlchemy async, pytest/pytest-asyncio, testcontainers-Postgres.

## Global Constraints

- **Human authority is final and exclusive** (ADR-0005, INV-07): this code never computes or phrases a Bid/No-Bid/Go/No-Go verdict itself — `BidReadinessCandidate` is a layer-3 derived fact (coverage %, lottery flag, critical lines), `Decision` is the layer-4 human record (ADR-0003), and only a human actor (resolved via `packages/platform/rbac`, never a default identity) can create a `Decision` row.
- **Decisions are append-only** — no `UPDATE`/`DELETE` statement against the `decisions` table is ever issued by application code. A later reversal (P316's Conditional Bid auto-transitioning to No-Bid) is a new row, not a mutation.
- **Never invent a number.** Qualification/financing/customer-reputation/margin/risk-concentration/resource-loading scoring has no source-supplied formula and is NOT computed — a human enters free-text notes for these; the one real number this plan computes (BOQ coverage vs. the "~85%" lottery threshold) is copied verbatim from `TENDER_INTELLIGENCE_SPEC.md` §7.1's own text, not invented here.
- **Use the real `tenders`/`tender_versions` identity** (ADR-0001: one authoritative entity per business fact) — every new table references `tenders.id` (`tender_id`), never a free-text tender identifier that would shadow it.
- Follow existing code style exactly: frozen dataclasses for pure models, `from __future__ import annotations`, SQLAlchemy `text()` queries returning `list[dict]`/scalar via `.mappings()`/`.scalar_one()`, JSONB columns read back with `json.loads()` only `if isinstance(value, str)` (see `packages/tender/signals_store.py`), idempotency-key + RBAC `require_permission` pattern from `apps/api_tender/routers/admin_users.py` for every mutating route, comments only for non-obvious *why*.

---

## Scope note (record before writing code)

- **Built:** `GoNoGoInputs` (human free-text record), `BidReadinessCandidate` (BOQ coverage % + lottery flag + single-vendor-critical lines, computed live from real persisted BOQ lines + a real vendor-offer fetch), append-only `Decision` record, `LockInRequirement` auto-flagging (INV-20's *identification* half only) on a Bid/Conditional Bid decision.
- **Deliberately not built (recorded in Task 6, not silently approximated):**
  1. Any scoring/weighting of qualification, financing, customer reputation, margin, risk concentration, or own-resource-loading — no source document supplies these, and customer reputation specifically depends on Phase 4.C's Execution Ledger, which does not exist yet.
  2. P316's "three probabilities" — no calibrated probability source exists (DFE's own `forecast_card.py` already defers this, per its own docstring).
  3. INV-20's actual LOI/pre-order **document generation** — only the flagging (which BOQ lines need one, for which vendor) is built.
  4. INV-06's No-Go override maker/checker flow — this task builds `no_go` as one of five possible `Decision` types; a distinct *override* flow for reversing an active No-Go is not built.
  5. The bid-readiness endpoint hardcodes `data_realm="vendor-sandbox"` — the only realm with any data today (ADR-0004); revisit once `vendor-production` exists.

---

## File Structure

- **Modify** `packages/decision/matching.py` — rename `_is_strong_source` → public `is_strong_source` (task 4.A's critical-line detection needs it too; keeping it private would duplicate the gating logic in two places).
- **Modify** `packages/tender/boq_lines_store.py` — add `list_boq_lines_by_tender_version()`.
- **Modify** `packages/tender/normalized.py` — add `get_current_tender_version_id()`.
- **Create** `packages/decision/decision_model.py` — `GoNoGoInputs`, `Decision`, `DECISION_TYPES`, `LockInRequirement` (pure dataclasses).
- **Create** `packages/decision/bid_readiness.py` — `CriticalLine`, `BidReadinessCandidate`, `build_bid_readiness_candidate()` (pure).
- **Create** `migrations/0014_decision_core.sql` — `go_no_go_inputs`, `bid_readiness_candidates`, `decisions`, `lock_in_requirements`.
- **Create** `packages/decision/decision_store.py` — persistence, append-only for `decisions`.
- **Modify** `packages/platform/settings.py` — bump `expected_schema_version` default 13→14; add `vendor_service_base_url`.
- **Modify** `apps/api_tender/deps.py` — add `get_vendor_http_client()` (test-overridable, mirrors `get_connection`'s DI shape).
- **Create** `apps/api_tender/routers/decision.py` — 3 endpoints, registered in `apps/api_tender/main.py`.
- **Test:** `tests/unit/test_bid_readiness.py`, `tests/unit/test_decision_model.py`, `tests/integration/test_boq_lines_store.py` (extend), `tests/integration/test_decision_api.py`, plus the usual schema-version-13→14 test updates (`tests/integration/test_migrations_runner.py`, `tests/integration/test_api_tender_health.py`, `tests/integration/test_api_vendor_health.py`).

---

### Task 1: `is_strong_source` goes public; new BOQ-line and tender-version query helpers

**Files:**
- Modify: `packages/decision/matching.py`
- Modify: `packages/tender/boq_lines_store.py`
- Modify: `packages/tender/normalized.py`
- Test: `tests/unit/test_matching.py` (rename reference), `tests/integration/test_boq_lines_store.py`, `tests/integration/test_normalized.py`

**Interfaces:**
- Consumes: existing `MatchCandidate`, `boq_lines`/`tender_versions`/`tenders` tables (migrations 0003, 0007).
- Produces: `is_strong_source(candidate: MatchCandidate) -> bool` (public, same body as the old `_is_strong_source`); `list_boq_lines_by_tender_version(conn: AsyncConnection, *, tender_version_id: int) -> list[BoqLine]`; `get_current_tender_version_id(conn: AsyncConnection, *, tender_id: int) -> int | None`. Task 2 depends on `is_strong_source`'s exact name; Task 4's router depends on both query functions.

- [ ] **Step 1: Write the failing tests**

In `tests/unit/test_matching.py`, find every occurrence of `_is_strong_source` in test code (there should be none directly — tests call `match_boq_line`/`classify_candidate`, not the private helper). Confirm this by running:
```bash
grep -n "_is_strong_source" tests/unit/test_matching.py
```
If the grep is empty, no test file change is needed for the rename itself — skip to Step 3. (This step just confirms there's nothing to break.)

Add to `tests/integration/test_boq_lines_store.py` (open the file first to match its existing imports/fixtures — it already has tests for `store_boq_lines`, follow the same `engine` fixture pattern):

```python
async def test_list_boq_lines_by_tender_version_returns_stored_lines(engine):
    from decimal import Decimal

    from packages.tender.boq_line_model import BoqLine
    from packages.tender.boq_lines_store import list_boq_lines_by_tender_version, store_boq_lines
    from packages.tender.normalized import create_normalized_version, get_or_create_tender
    from packages.tender.raw_snapshot import store_raw_snapshot

    line = BoqLine(
        source_line_id=501,
        page_number=1,
        section="Section A",
        category_code=None,
        description="rebar-12mm reinforcement steel",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )

    async with engine.begin() as conn:
        raw_snapshot_id = await store_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-event-4a",
            body={"eventId": 999001},
            contract_version="v1",
            correlation_id="test-4a",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-event-4a")
        version_id = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=999001,
            tender_version_id=version_id,
            raw_snapshot_id=raw_snapshot_id,
            lines=[line],
        )
        result = await list_boq_lines_by_tender_version(conn, tender_version_id=version_id)

    assert len(result) == 1
    assert result[0].source_line_id == 501
    assert result[0].description == "rebar-12mm reinforcement steel"
    assert result[0].qty == Decimal("10")
    assert result[0].amount == Decimal("8500")
```

Run this test first to confirm your assumed signatures for `store_raw_snapshot`/`get_or_create_tender`/`create_normalized_version` are correct — if any signature differs, read that module directly and adjust the test's fixture setup accordingly (do not guess further; these three functions already exist and are exercised by other integration tests you can check, e.g. `tests/integration/test_boq_lines_storage.py`).

Add to `tests/integration/test_normalized.py` (open it first to match style):

```python
async def test_get_current_tender_version_id_returns_the_current_version(engine):
    from packages.tender.normalized import create_normalized_version, get_current_tender_version_id, get_or_create_tender
    from packages.tender.raw_snapshot import store_raw_snapshot

    async with engine.begin() as conn:
        raw_snapshot_id = await store_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-event-4a-version",
            body={"eventId": 999002},
            contract_version="v1",
            correlation_id="test-4a-version",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-event-4a-version")
        version_id = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        current_version_id = await get_current_tender_version_id(conn, tender_id=tender_id)

    assert current_version_id == version_id


async def test_get_current_tender_version_id_returns_none_for_unknown_tender(engine):
    from packages.tender.normalized import get_current_tender_version_id

    async with engine.begin() as conn:
        result = await get_current_tender_version_id(conn, tender_id=999999999)

    assert result is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/integration/test_boq_lines_store.py tests/integration/test_normalized.py -q -k "4a or tender_version_id"`
Expected: FAIL with `ImportError`/`AttributeError` for the two missing functions.

- [ ] **Step 3: Write the minimal implementation**

In `packages/decision/matching.py`, rename `_is_strong_source` to `is_strong_source` everywhere it's defined and called (the function body is unchanged):

```python
def is_strong_source(candidate: MatchCandidate) -> bool:
    return (
        candidate.volume_status == "sufficient"
        and candidate.freshness == "fresh"
        and candidate.effective_executable_status in ("reserved", "confirmed")
    )
```
Update its two call sites (`_traffic_light`, `rank_executable_candidates_by_tco`) to call `is_strong_source(...)` instead of `_is_strong_source(...)`.

Add to `packages/tender/boq_lines_store.py`, after `store_boq_lines`:

```python
from decimal import Decimal

from sqlalchemy.ext.asyncio import AsyncConnection

from .boq_line_model import BoqLine, SpecRequirement


async def list_boq_lines_by_tender_version(conn: AsyncConnection, *, tender_version_id: int) -> list[BoqLine]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT page_number, source_line_id, section, category_code, description, unit_raw,
                           unit_canonical, unit_status, qty, line_type, spec_requirements, rate, amount
                    FROM boq_lines WHERE tender_version_id = :tender_version_id ORDER BY source_line_id
                    """
                ),
                {"tender_version_id": tender_version_id},
            )
        )
        .mappings()
        .all()
    )
    lines: list[BoqLine] = []
    for row in rows:
        raw_specs = row["spec_requirements"]
        if isinstance(raw_specs, str):
            raw_specs = json.loads(raw_specs)
        lines.append(
            BoqLine(
                source_line_id=row["source_line_id"],
                page_number=row["page_number"],
                section=row["section"],
                category_code=row["category_code"],
                description=row["description"],
                unit_raw=row["unit_raw"],
                unit_canonical=row["unit_canonical"],
                unit_status=row["unit_status"],
                qty=row["qty"],
                line_type=row["line_type"],
                spec_requirements=tuple(SpecRequirement(kind=s["kind"], raw_text=s["raw_text"]) for s in raw_specs),
                rate=row["rate"],
                amount=row["amount"],
            )
        )
    return lines
```
(Add `from decimal import Decimal` only if not already imported — check the top of the file first; `Decimal` may already be unused here since `qty`/`rate`/`amount` come back from asyncpg as `Decimal` natively for `NUMERIC` columns, no manual cast needed. Remove the unused import if `ruff check` flags it.)

Add to `packages/tender/normalized.py`, after `get_or_create_tender`:

```python
async def get_current_tender_version_id(conn: AsyncConnection, *, tender_id: int) -> int | None:
    row = (await conn.execute(text("SELECT current_version_id FROM tenders WHERE id = :id"), {"id": tender_id})).first()
    if row is None:
        return None
    return row[0]
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_boq_lines_store.py tests/integration/test_normalized.py tests/unit/test_matching.py -q`
Expected: PASS (all tests, including pre-existing ones — the rename must not break `_traffic_light`/`rank_executable_candidates_by_tco`'s existing behavior).

- [ ] **Step 5: Commit**

```bash
git add packages/decision/matching.py packages/tender/boq_lines_store.py packages/tender/normalized.py tests/integration/test_boq_lines_store.py tests/integration/test_normalized.py
git commit -m "feat(tender,decision): BOQ-line-by-version lookup, current-tender-version lookup, public is_strong_source (task 4.A prep)"
```

---

### Task 2: Pure domain models — `GoNoGoInputs`/`Decision`/`LockInRequirement`, `BidReadinessCandidate`

**Files:**
- Create: `packages/decision/decision_model.py`
- Create: `packages/decision/bid_readiness.py`
- Test: `tests/unit/test_decision_model.py`, `tests/unit/test_bid_readiness.py`

**Interfaces:**
- Consumes: `packages.decision.matching.{BoqLineMatch, MatchCandidate, is_strong_source, match_boq_line}`, `packages.decision.boq_summary.{BoqMatchSummary, summarize_boq_matches}`, `packages.tender.boq_line_model.BoqLine`, `packages.contracts.vendor_api.VendorOfferDTO`.
- Produces:
  - `DECISION_TYPES = ("go", "no_go", "bid", "no_bid", "conditional_bid")`
  - `GoNoGoInputs` (frozen dataclass): `tender_id: int, company_profile_notes: str, qualification_notes: str, financing_notes: str, customer_reputation_notes: str, pre_designated_winner_suspected: bool, entered_by: str, entered_at: str`
  - `Decision` (frozen dataclass): `tender_id: int, decision_type: str, conditions: tuple[str, ...], deadline: str | None, justification: str, actor: str, decided_at: str, go_no_go_inputs_id: int | None, bid_readiness_candidate_id: int | None` — `__post_init__` raises `ValueError` if `decision_type not in DECISION_TYPES`.
  - `LockInRequirement` (frozen dataclass): `tender_id: int, decision_id: int, boqline_source_line_id: int, vendor_id: int, vendor_name: str`
  - `CriticalLine` (frozen dataclass): `boqline_source_line_id: int, vendor_id: int, vendor_name: str`
  - `BidReadinessCandidate` (frozen dataclass): `tender_id: int, summary: BoqMatchSummary, is_lottery: bool, critical_lines: tuple[CriticalLine, ...], computed_at: str`
  - `LOTTERY_COVERAGE_THRESHOLD_PCT = 85.0`
  - `build_bid_readiness_candidate(tender_id: int, boq_lines: list[BoqLine], offers: list[VendorOfferDTO], *, as_of: datetime, computed_at: str) -> BidReadinessCandidate`

  Task 3's store module depends on every field name above exactly. Task 4's router depends on `build_bid_readiness_candidate`'s signature and `DECISION_TYPES`.

- [ ] **Step 1: Write the failing tests**

Create `tests/unit/test_decision_model.py`:

```python
"""Unit tests for packages/decision/decision_model.py (task 4.A,
TENDER_INTELLIGENCE_SPEC.md §7.1/§8: Decision is append-only, human-authored,
ADR-0003 layer 4 / ADR-0005 human-authority-exclusive)."""

from __future__ import annotations

import pytest

from packages.decision.decision_model import DECISION_TYPES, Decision, GoNoGoInputs, LockInRequirement


def test_decision_types_are_exactly_the_five_named_in_the_spec():
    assert set(DECISION_TYPES) == {"go", "no_go", "bid", "no_bid", "conditional_bid"}


def test_decision_accepts_a_known_type():
    decision = Decision(
        tender_id=1,
        decision_type="conditional_bid",
        conditions=("lock rebar price by Friday",),
        deadline="2026-08-14T00:00:00+00:00",
        justification="91% BOQ coverage, 14-16% margin",
        actor="pm-1",
        decided_at="2026-08-08T00:00:00+00:00",
        go_no_go_inputs_id=1,
        bid_readiness_candidate_id=1,
    )
    assert decision.decision_type == "conditional_bid"


def test_decision_rejects_an_unknown_type():
    with pytest.raises(ValueError, match="unknown decision_type"):
        Decision(
            tender_id=1,
            decision_type="maybe",
            conditions=(),
            deadline=None,
            justification="x",
            actor="pm-1",
            decided_at="2026-08-08T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=None,
        )


def test_go_no_go_inputs_is_a_plain_record():
    inputs = GoNoGoInputs(
        tender_id=1,
        company_profile_notes="20 years in market",
        qualification_notes="all licenses current",
        financing_notes="bond available",
        customer_reputation_notes="pays on time historically",
        pre_designated_winner_suspected=False,
        entered_by="pm-1",
        entered_at="2026-08-08T00:00:00+00:00",
    )
    assert inputs.pre_designated_winner_suspected is False


def test_lock_in_requirement_is_a_plain_record():
    lock_in = LockInRequirement(tender_id=1, decision_id=1, boqline_source_line_id=501, vendor_id=7, vendor_name="Vendor A")
    assert lock_in.vendor_id == 7
```

Create `tests/unit/test_bid_readiness.py`:

```python
"""Unit tests for packages/decision/bid_readiness.py (task 4.A,
TENDER_INTELLIGENCE_SPEC.md §7.1's Bid/No-Bid coverage rule: "покрытие BOQ
в деньгах 🟢+🟡 < ~85% -> участие = лотерея"). Pure functions, no DB --
reuses packages/decision/matching.py's own real match_boq_line, not a
hand-rolled reimplementation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from packages.contracts.vendor_api import VendorOfferDTO
from packages.decision.bid_readiness import LOTTERY_COVERAGE_THRESHOLD_PCT, build_bid_readiness_candidate
from packages.tender.boq_line_model import BoqLine

AS_OF = datetime.fromisoformat("2026-08-08T00:00:00+00:00")


def _boq_line(source_line_id: int, description: str, amount: str, line_type: str = "normal") -> BoqLine:
    return BoqLine(
        source_line_id=source_line_id,
        page_number=1,
        section=None,
        category_code=None,
        description=description,
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type=line_type,
        spec_requirements=(),
        rate=Decimal("100"),
        amount=Decimal(amount),
    )


def _offer(
    vendor_id: int,
    vendor_name: str,
    material: str,
    *,
    has_positive_reputation: bool = False,
    executable_status: str = "reserved",
) -> VendorOfferDTO:
    return VendorOfferDTO(
        id=vendor_id,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material=material,
        price=100.0,
        currency="AZN",
        vat_rate=18.0,
        uom="t",
        uom_canonical_qty=1.0,
        moq=1.0,
        capacity=100.0,
        inventory=40.0,
        valid_from="2026-08-01T00:00:00+00:00",
        valid_until="2026-09-01T00:00:00+00:00",
        evidence_source="test",
        observed_at="2026-08-01T00:00:00+00:00",
        adverse_case=None,
        executable_status=executable_status,
        effective_executable_status=executable_status,
        has_positive_reputation=has_positive_reputation,
        has_negative_reputation=False,
    )


def test_full_coverage_with_two_strong_vendors_is_not_a_lottery():
    boq_lines = [_boq_line(1, "rebar-12mm", "1000")]
    offers = [
        _offer(1, "Vendor A", "rebar-12mm", has_positive_reputation=True),
        _offer(2, "Vendor B", "rebar-12mm"),
    ]

    candidate = build_bid_readiness_candidate(
        42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00"
    )

    assert candidate.tender_id == 42
    assert candidate.summary.green_pct == 100.0
    assert candidate.is_lottery is False
    assert candidate.critical_lines == ()


def test_zero_coverage_is_a_lottery():
    boq_lines = [_boq_line(1, "excavation works", "1000")]
    offers = [_offer(1, "Vendor A", "rebar-12mm")]

    candidate = build_bid_readiness_candidate(
        42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00"
    )

    assert candidate.summary.red_pct == 100.0
    assert candidate.is_lottery is True


def test_lottery_threshold_matches_the_spec_constant():
    assert LOTTERY_COVERAGE_THRESHOLD_PCT == 85.0


def test_single_vendor_line_is_flagged_critical():
    boq_lines = [_boq_line(1, "rebar-12mm", "1000")]
    offers = [_offer(1, "Vendor A", "rebar-12mm")]

    candidate = build_bid_readiness_candidate(
        42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00"
    )

    assert len(candidate.critical_lines) == 1
    assert candidate.critical_lines[0].boqline_source_line_id == 1
    assert candidate.critical_lines[0].vendor_id == 1


def test_two_strong_vendor_line_is_not_flagged_critical():
    boq_lines = [_boq_line(1, "rebar-12mm", "1000")]
    offers = [
        _offer(1, "Vendor A", "rebar-12mm", has_positive_reputation=True),
        _offer(2, "Vendor B", "rebar-12mm"),
    ]

    candidate = build_bid_readiness_candidate(
        42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00"
    )

    assert candidate.critical_lines == ()


def test_non_matchable_line_type_is_excluded_and_not_critical():
    boq_lines = [_boq_line(1, "preliminaries and general conditions", "500", line_type="preliminaries")]
    offers = [_offer(1, "Vendor A", "rebar-12mm")]

    candidate = build_bid_readiness_candidate(
        42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00"
    )

    assert candidate.summary.non_matchable_line_count == 1
    assert candidate.critical_lines == ()
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_decision_model.py tests/unit/test_bid_readiness.py -q`
Expected: FAIL with `ModuleNotFoundError` for both new modules.

- [ ] **Step 3: Write the minimal implementation**

Create `packages/decision/decision_model.py`:

```python
"""Decision Core domain model (task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1,
§8's `Decision` entity, ADR-0003 layer 4, ADR-0005). Pure dataclasses, no
DB -- packages/decision/decision_store.py persists these.

`Decision` is append-only by construction of the store layer (no UPDATE
statement exists for it) -- this module only guards that `decision_type`
is one of the five values TENDER_INTELLIGENCE_SPEC.md §7.1 actually names
(Go/No-Go's two, Bid/No-Bid/Conditional's three), raising rather than
silently accepting an arbitrary string (AGENTS.md hard ban #3).

`GoNoGoInputs` carries only free-text notes for qualification/financing/
customer-reputation/pre-designated-winner-suspicion -- none of these are
scored or weighted here. No source document supplies a scoring formula for
any of them (customer reputation specifically depends on Phase 4.C's
Execution Ledger, which does not exist yet), so a human enters an
assessment as text and makes the actual Go/No-Go call themselves; this
module only gives that assessment a durable, queryable home."""

from __future__ import annotations

from dataclasses import dataclass

DECISION_TYPES = ("go", "no_go", "bid", "no_bid", "conditional_bid")


@dataclass(frozen=True)
class GoNoGoInputs:
    tender_id: int
    company_profile_notes: str
    qualification_notes: str
    financing_notes: str
    customer_reputation_notes: str
    pre_designated_winner_suspected: bool
    entered_by: str
    entered_at: str


@dataclass(frozen=True)
class Decision:
    tender_id: int
    decision_type: str
    conditions: tuple[str, ...]
    deadline: str | None
    justification: str
    actor: str
    decided_at: str
    go_no_go_inputs_id: int | None
    bid_readiness_candidate_id: int | None

    def __post_init__(self) -> None:
        if self.decision_type not in DECISION_TYPES:
            raise ValueError(f"unknown decision_type: {self.decision_type!r}")


@dataclass(frozen=True)
class LockInRequirement:
    tender_id: int
    decision_id: int
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str
```

Create `packages/decision/bid_readiness.py`:

```python
"""Bid readiness computation (task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1):
the one real, computable half of Bid/No-Bid -- BOQ money coverage against
the spec's own "~85%" lottery threshold, and which BOQ lines depend on
exactly one strong (executable, per task 3.C's Executable Availability)
vendor. Margin, risk concentration, and own-resource-loading are NOT
computed here -- no source document supplies the company's own cost basis
or resource schedule needed for any of them.

`LOTTERY_COVERAGE_THRESHOLD_PCT = 85.0` is copied verbatim from
TENDER_INTELLIGENCE_SPEC.md §7.1 ("покрытие BOQ в деньгах 🟢+🟡 < ~85% ->
участие = лотерея") -- a source-supplied approximate number, not invented
by this task (AGENTS.md hard ban #2 forbids inventing a number nobody
supplied; it does not forbid using one the source document already gives,
tilde and all).

A "critical" line is one where exactly one distinct vendor_id is a strong
source (packages/decision/matching.py::is_strong_source) -- this directly
implements §7.1's Bid/No-Bid criterion "зависимость от единственного
вендора по критической позиции" from data already computed by task 3.D's
matching.py, not a new signal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from packages.contracts.vendor_api import VendorOfferDTO
from packages.decision.boq_summary import BoqMatchSummary, summarize_boq_matches
from packages.decision.matching import BoqLineMatch, is_strong_source, match_boq_line
from packages.tender.boq_line_model import BoqLine

LOTTERY_COVERAGE_THRESHOLD_PCT = 85.0


@dataclass(frozen=True)
class CriticalLine:
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str


@dataclass(frozen=True)
class BidReadinessCandidate:
    tender_id: int
    summary: BoqMatchSummary
    is_lottery: bool
    critical_lines: tuple[CriticalLine, ...]
    computed_at: str


def _critical_lines(matches: dict[int, BoqLineMatch]) -> tuple[CriticalLine, ...]:
    critical: list[CriticalLine] = []
    for match in matches.values():
        strong = [c for c in match.candidates if is_strong_source(c)]
        distinct_vendors = {c.vendor_id for c in strong}
        if len(distinct_vendors) == 1:
            sole = strong[0]
            critical.append(
                CriticalLine(
                    boqline_source_line_id=match.boqline_source_line_id,
                    vendor_id=sole.vendor_id,
                    vendor_name=sole.vendor_name,
                )
            )
    return tuple(critical)


def build_bid_readiness_candidate(
    tender_id: int,
    boq_lines: list[BoqLine],
    offers: list[VendorOfferDTO],
    *,
    as_of: datetime,
    computed_at: str,
) -> BidReadinessCandidate:
    matches = {
        line.source_line_id: match_boq_line(line, offers, as_of=as_of) for line in boq_lines if line.line_type == "normal"
    }
    summary = summarize_boq_matches(boq_lines, matches)
    coverage_pct = summary.green_pct + summary.yellow_pct
    return BidReadinessCandidate(
        tender_id=tender_id,
        summary=summary,
        is_lottery=coverage_pct < LOTTERY_COVERAGE_THRESHOLD_PCT,
        critical_lines=_critical_lines(matches),
        computed_at=computed_at,
    )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_decision_model.py tests/unit/test_bid_readiness.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/decision/decision_model.py packages/decision/bid_readiness.py tests/unit/test_decision_model.py tests/unit/test_bid_readiness.py
git commit -m "feat(decision): Decision/GoNoGoInputs/LockInRequirement models, bid-readiness computation (task 4.A, P316 prep)"
```

---

### Task 3: Migration + persistence

**Files:**
- Create: `migrations/0014_decision_core.sql`
- Create: `packages/decision/decision_store.py`
- Modify: `packages/platform/settings.py`
- Test: `tests/integration/test_decision_store.py`, plus schema-version bump updates below

**Interfaces:**
- Consumes: `packages.decision.decision_model.{Decision, GoNoGoInputs, LockInRequirement}`, `packages.decision.bid_readiness.BidReadinessCandidate`.
- Produces: `store_go_no_go_inputs(conn, inputs: GoNoGoInputs) -> int`; `store_bid_readiness_candidate(conn, candidate: BidReadinessCandidate) -> int`; `load_bid_readiness_candidate(conn, candidate_id: int) -> dict[str, Any]` (raises `ValueError` if not found; `critical_lines` key is a `list[dict]` with `boqline_source_line_id`/`vendor_id`/`vendor_name`); `store_decision(conn, decision: Decision) -> int`; `store_lock_in_requirement(conn, *, tender_id: int, decision_id: int, boqline_source_line_id: int, vendor_id: int, vendor_name: str) -> int`; `list_lock_in_requirements_by_tender(conn, *, tender_id: int) -> list[dict[str, Any]]`.

  Task 4's router depends on every function name/signature above exactly.

- [ ] **Step 1: Write the failing test**

Create `tests/integration/test_decision_store.py`:

```python
"""Integration tests for packages/decision/decision_store.py (task 4.A).
Append-only for `decisions`: this file does not test any UPDATE/DELETE
because none exists to test -- see decision_store.py's module docstring."""

from __future__ import annotations

from decimal import Decimal

from packages.decision.bid_readiness import BidReadinessCandidate, CriticalLine
from packages.decision.boq_summary import BoqMatchSummary
from packages.decision.decision_model import Decision, GoNoGoInputs, LockInRequirement
from packages.decision.decision_store import (
    list_lock_in_requirements_by_tender,
    load_bid_readiness_candidate,
    store_bid_readiness_candidate,
    store_decision,
    store_go_no_go_inputs,
    store_lock_in_requirement,
)
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import store_raw_snapshot


async def _make_tender(conn, identity_key: str) -> int:
    raw_snapshot_id = await store_raw_snapshot(
        conn,
        source="etender",
        resource_type="event_details",
        identity_key=identity_key,
        body={"eventId": 1},
        contract_version="v1",
        correlation_id="test-decision-store",
    )
    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)
    await create_normalized_version(
        conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
    )
    return tender_id


async def test_go_no_go_inputs_round_trips(engine):
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-1")
        inputs = GoNoGoInputs(
            tender_id=tender_id,
            company_profile_notes="20 years in market",
            qualification_notes="all licenses current",
            financing_notes="bond available",
            customer_reputation_notes="pays on time",
            pre_designated_winner_suspected=False,
            entered_by="pm-1",
            entered_at="2026-08-08T00:00:00+00:00",
        )
        inputs_id = await store_go_no_go_inputs(conn, inputs)

    assert isinstance(inputs_id, int)


async def test_bid_readiness_candidate_round_trips_with_critical_lines(engine):
    summary = BoqMatchSummary(
        green_amount=Decimal("1000"),
        yellow_amount=Decimal("0"),
        red_amount=Decimal("0"),
        unpriced_line_count=0,
        non_matchable_line_count=0,
        non_matchable_amount=Decimal("0"),
        total_priced_amount=Decimal("1000"),
        green_pct=100.0,
        yellow_pct=0.0,
        red_pct=0.0,
    )
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-2")
        candidate = BidReadinessCandidate(
            tender_id=tender_id,
            summary=summary,
            is_lottery=False,
            critical_lines=(CriticalLine(boqline_source_line_id=1, vendor_id=7, vendor_name="Vendor A"),),
            computed_at="2026-08-08T00:00:00+00:00",
        )
        candidate_id = await store_bid_readiness_candidate(conn, candidate)
        loaded = await load_bid_readiness_candidate(conn, candidate_id)

    assert loaded["tender_id"] == tender_id
    assert loaded["critical_lines"] == [{"boqline_source_line_id": 1, "vendor_id": 7, "vendor_name": "Vendor A"}]


async def test_decision_rejects_at_the_model_layer_not_silently_in_the_db(engine):
    # Decision.__post_init__ already raises for an unknown decision_type
    # (tested in test_decision_model.py) -- this test only proves the
    # store layer round-trips a VALID decision correctly, including
    # conditions as a real list, not a string.
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-3")
        decision = Decision(
            tender_id=tender_id,
            decision_type="conditional_bid",
            conditions=("lock rebar price by Friday", "find backup crane owner"),
            deadline="2026-08-14T00:00:00+00:00",
            justification="91% coverage, 14-16% margin",
            actor="pm-1",
            decided_at="2026-08-08T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=None,
        )
        decision_id = await store_decision(conn, decision)

    assert isinstance(decision_id, int)


async def test_lock_in_requirements_round_trip_by_tender(engine):
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-4")
        decision = Decision(
            tender_id=tender_id,
            decision_type="bid",
            conditions=(),
            deadline=None,
            justification="full coverage",
            actor="pm-1",
            decided_at="2026-08-08T00:00:00+00:00",
            go_no_go_inputs_id=None,
            bid_readiness_candidate_id=None,
        )
        decision_id = await store_decision(conn, decision)
        await store_lock_in_requirement(
            conn, tender_id=tender_id, decision_id=decision_id, boqline_source_line_id=1, vendor_id=7, vendor_name="Vendor A"
        )
        lock_ins = await list_lock_in_requirements_by_tender(conn, tender_id=tender_id)

    assert len(lock_ins) == 1
    assert lock_ins[0]["status"] == "pending"
    assert lock_ins[0]["vendor_name"] == "Vendor A"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_decision_store.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.decision.decision_store'` (and the migration doesn't exist yet, so table lookups would fail too once the module exists — write the migration first, per Step 3 below, before running this).

- [ ] **Step 3: Write the minimal implementation**

Create `migrations/0014_decision_core.sql`:

```sql
-- Decision Core (Phase 4, task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1):
-- human Go/No-Go inputs, the one real derived Bid/No-Bid signal (BOQ money
-- coverage + single-vendor-critical lines), the append-only human Decision
-- record (ADR-0003 layer 4, ADR-0005: human authority is final and
-- exclusive), and INV-20's lock-in flagging for single-vendor-critical
-- BOQ lines on a Bid/Conditional Bid decision. Every table references the
-- real `tenders` identity (ADR-0001) -- no free-text tender identifier is
-- introduced alongside it.

CREATE TABLE go_no_go_inputs (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    company_profile_notes TEXT NOT NULL,
    qualification_notes TEXT NOT NULL,
    financing_notes TEXT NOT NULL,
    customer_reputation_notes TEXT NOT NULL,
    pre_designated_winner_suspected BOOLEAN NOT NULL,
    entered_by TEXT NOT NULL,
    entered_at TIMESTAMPTZ NOT NULL
);

CREATE TABLE bid_readiness_candidates (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    green_amount NUMERIC NOT NULL,
    yellow_amount NUMERIC NOT NULL,
    red_amount NUMERIC NOT NULL,
    unpriced_line_count INTEGER NOT NULL,
    non_matchable_line_count INTEGER NOT NULL,
    non_matchable_amount NUMERIC NOT NULL,
    total_priced_amount NUMERIC NOT NULL,
    green_pct DOUBLE PRECISION NOT NULL,
    yellow_pct DOUBLE PRECISION NOT NULL,
    red_pct DOUBLE PRECISION NOT NULL,
    is_lottery BOOLEAN NOT NULL,
    critical_lines JSONB NOT NULL,
    computed_at TIMESTAMPTZ NOT NULL
);

-- Append-only (ADR-0003 layer 4, ADR-0005): application code never issues
-- an UPDATE/DELETE against this table. A later reversal (P316's
-- Conditional Bid auto-transitioning to No-Bid) is a new row.
CREATE TABLE decisions (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    decision_type TEXT NOT NULL CHECK (decision_type IN ('go', 'no_go', 'bid', 'no_bid', 'conditional_bid')),
    conditions JSONB NOT NULL,
    deadline TIMESTAMPTZ,
    justification TEXT NOT NULL,
    actor TEXT NOT NULL,
    decided_at TIMESTAMPTZ NOT NULL,
    go_no_go_inputs_id BIGINT REFERENCES go_no_go_inputs (id),
    bid_readiness_candidate_id BIGINT REFERENCES bid_readiness_candidates (id)
);

-- INV-20 lock-in: auto-generated when a Bid/Conditional Bid decision names
-- a single-vendor-critical BOQ line. Only identification/flagging is built
-- here -- actual LOI/pre-order document generation is out of scope
-- (docs/decisions/OPEN-QUESTIONS.md).
CREATE TABLE lock_in_requirements (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    decision_id BIGINT NOT NULL REFERENCES decisions (id),
    boqline_source_line_id BIGINT NOT NULL,
    vendor_id BIGINT NOT NULL,
    vendor_name TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending', 'locked', 'expired')),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX lock_in_requirements_tender_idx ON lock_in_requirements (tender_id);
```

Create `packages/decision/decision_store.py`:

```python
"""Decision Core persistence (task 4.A). Append-only for `decisions` --
no UPDATE/DELETE statement against that table is ever issued here."""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .bid_readiness import BidReadinessCandidate
from .decision_model import Decision, GoNoGoInputs


async def store_go_no_go_inputs(conn: AsyncConnection, inputs: GoNoGoInputs) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO go_no_go_inputs
                    (tender_id, company_profile_notes, qualification_notes, financing_notes,
                     customer_reputation_notes, pre_designated_winner_suspected, entered_by, entered_at)
                VALUES (:tender_id, :company_profile_notes, :qualification_notes, :financing_notes,
                        :customer_reputation_notes, :pre_designated_winner_suspected, :entered_by, :entered_at)
                RETURNING id
                """
            ),
            {
                "tender_id": inputs.tender_id,
                "company_profile_notes": inputs.company_profile_notes,
                "qualification_notes": inputs.qualification_notes,
                "financing_notes": inputs.financing_notes,
                "customer_reputation_notes": inputs.customer_reputation_notes,
                "pre_designated_winner_suspected": inputs.pre_designated_winner_suspected,
                "entered_by": inputs.entered_by,
                "entered_at": datetime.fromisoformat(inputs.entered_at),
            },
        )
    ).scalar_one()


async def store_bid_readiness_candidate(conn: AsyncConnection, candidate: BidReadinessCandidate) -> int:
    critical_lines_json = json.dumps(
        [
            {"boqline_source_line_id": cl.boqline_source_line_id, "vendor_id": cl.vendor_id, "vendor_name": cl.vendor_name}
            for cl in candidate.critical_lines
        ]
    )
    return (
        await conn.execute(
            text(
                """
                INSERT INTO bid_readiness_candidates
                    (tender_id, green_amount, yellow_amount, red_amount, unpriced_line_count,
                     non_matchable_line_count, non_matchable_amount, total_priced_amount,
                     green_pct, yellow_pct, red_pct, is_lottery, critical_lines, computed_at)
                VALUES (:tender_id, :green_amount, :yellow_amount, :red_amount, :unpriced_line_count,
                        :non_matchable_line_count, :non_matchable_amount, :total_priced_amount,
                        :green_pct, :yellow_pct, :red_pct, :is_lottery, CAST(:critical_lines AS jsonb), :computed_at)
                RETURNING id
                """
            ),
            {
                "tender_id": candidate.tender_id,
                "green_amount": candidate.summary.green_amount,
                "yellow_amount": candidate.summary.yellow_amount,
                "red_amount": candidate.summary.red_amount,
                "unpriced_line_count": candidate.summary.unpriced_line_count,
                "non_matchable_line_count": candidate.summary.non_matchable_line_count,
                "non_matchable_amount": candidate.summary.non_matchable_amount,
                "total_priced_amount": candidate.summary.total_priced_amount,
                "green_pct": candidate.summary.green_pct,
                "yellow_pct": candidate.summary.yellow_pct,
                "red_pct": candidate.summary.red_pct,
                "is_lottery": candidate.is_lottery,
                "critical_lines": critical_lines_json,
                "computed_at": datetime.fromisoformat(candidate.computed_at),
            },
        )
    ).scalar_one()


async def load_bid_readiness_candidate(conn: AsyncConnection, candidate_id: int) -> dict[str, Any]:
    row = (
        (
            await conn.execute(
                text("SELECT id, tender_id, critical_lines FROM bid_readiness_candidates WHERE id = :id"),
                {"id": candidate_id},
            )
        )
        .mappings()
        .first()
    )
    if row is None:
        raise ValueError(f"bid readiness candidate {candidate_id} not found")
    result = dict(row)
    if isinstance(result["critical_lines"], str):
        result["critical_lines"] = json.loads(result["critical_lines"])
    return result


async def store_decision(conn: AsyncConnection, decision: Decision) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO decisions
                    (tender_id, decision_type, conditions, deadline, justification, actor, decided_at,
                     go_no_go_inputs_id, bid_readiness_candidate_id)
                VALUES (:tender_id, :decision_type, CAST(:conditions AS jsonb), :deadline, :justification, :actor,
                        :decided_at, :go_no_go_inputs_id, :bid_readiness_candidate_id)
                RETURNING id
                """
            ),
            {
                "tender_id": decision.tender_id,
                "decision_type": decision.decision_type,
                "conditions": json.dumps(list(decision.conditions)),
                "deadline": datetime.fromisoformat(decision.deadline) if decision.deadline else None,
                "justification": decision.justification,
                "actor": decision.actor,
                "decided_at": datetime.fromisoformat(decision.decided_at),
                "go_no_go_inputs_id": decision.go_no_go_inputs_id,
                "bid_readiness_candidate_id": decision.bid_readiness_candidate_id,
            },
        )
    ).scalar_one()


async def store_lock_in_requirement(
    conn: AsyncConnection,
    *,
    tender_id: int,
    decision_id: int,
    boqline_source_line_id: int,
    vendor_id: int,
    vendor_name: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO lock_in_requirements
                    (tender_id, decision_id, boqline_source_line_id, vendor_id, vendor_name)
                VALUES (:tender_id, :decision_id, :boqline_source_line_id, :vendor_id, :vendor_name)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "decision_id": decision_id,
                "boqline_source_line_id": boqline_source_line_id,
                "vendor_id": vendor_id,
                "vendor_name": vendor_name,
            },
        )
    ).scalar_one()


async def list_lock_in_requirements_by_tender(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, decision_id, boqline_source_line_id, vendor_id, vendor_name, status, created_at
                    FROM lock_in_requirements WHERE tender_id = :tender_id ORDER BY id
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

In `packages/platform/settings.py`, change:
```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "13")))
```
to:
```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "14")))
```

Update every test that hardcodes `expected_schema_version=13` or asserts `current_version() == 13` to `14` instead — find them first:
```bash
grep -rln "expected_schema_version=13\|current_version() == 13" tests/
```
Update each occurrence found (this is the same mechanical bump every prior migration in this repo has done — see `git log -p migrations/0013_vendor_napkin_evidence.sql`'s sibling test diffs for the exact pattern if you want a reference).

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/integration/test_decision_store.py tests/integration/test_migrations_runner.py tests/integration/test_api_tender_health.py tests/integration/test_api_vendor_health.py -q`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add migrations/0014_decision_core.sql packages/decision/decision_store.py packages/platform/settings.py tests/integration/test_decision_store.py
git add -u tests/
git commit -m "feat(decision): Decision Core persistence, migration 0014, schema version 13->14 (task 4.A)"
```

---

### Task 4: API — Go/No-Go inputs, live bid-readiness candidate, decision recording

**Files:**
- Modify: `apps/api_tender/deps.py`
- Modify: `apps/api_tender/main.py`
- Create: `apps/api_tender/routers/decision.py`

**Interfaces:**
- Consumes: everything from Tasks 1-3, plus `packages.contracts.vendor_api.{list_vendor_offers, VendorApiError}`, `packages.platform.rbac.dependency.require_permission`, `packages.platform.idempotency.{IdempotencyStore, IdempotencyKeyReused, fingerprint}`, `packages.platform.errors.ApiError`.
- Produces: `get_vendor_http_client(request: Request) -> httpx.AsyncClient | None` (in `deps.py`); router `apps/api_tender/routers/decision.py` with prefix `/tenders/{tender_id}`:
  - `POST /tenders/{tender_id}/go-no-go-inputs` (permission `decision.go_no_go.create`)
  - `GET /tenders/{tender_id}/bid-readiness-candidate?as_of=<datetime>` (permission `decision.bid_readiness.read`)
  - `POST /tenders/{tender_id}/decisions` (permission `decision.decisions.create`)

  Task 5's tests depend on these three exact routes, their permission names, and the `get_vendor_http_client` override point.

- [ ] **Step 1: Write the failing test (route existence smoke check)**

This task's real behavioral tests are Task 5's job (they need the full app + a real in-process vendor app for the live bid-readiness call, which is more setup than belongs in a "write one failing test" step). For this task, confirm the routes don't exist yet with a minimal smoke check — create `tests/integration/test_decision_api_routes_exist.py`:

```python
"""Smoke check that task 4.A's three routes are registered (task 5 covers
real behavior). Run before Task 4's implementation to confirm the routes
are genuinely missing, and after to confirm they're wired -- this file is
superseded by tests/integration/test_decision_api.py in Task 5 and can be
deleted once that file exists and passes."""

from __future__ import annotations

import httpx

from apps.api_tender.main import create_app
from packages.platform.settings import Settings


async def test_go_no_go_inputs_route_is_registered(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tenders/1/go-no-go-inputs", json={}, headers={"Idempotency-Key": "k1"})
    assert response.status_code != 404


async def test_bid_readiness_candidate_route_is_registered(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/tenders/1/bid-readiness-candidate", params={"as_of": "2026-08-08T00:00:00Z"})
    assert response.status_code != 404


async def test_decisions_route_is_registered(engine, _database_url):
    settings = Settings(database_url=_database_url)
    app = create_app(settings)
    app.state.engine = engine
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post("/tenders/1/decisions", json={}, headers={"Idempotency-Key": "k1"})
    assert response.status_code != 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_decision_api_routes_exist.py -q`
Expected: FAIL — all three assert `!= 404` but currently get 404 (routes don't exist).

- [ ] **Step 3: Write the minimal implementation**

Add to `apps/api_tender/deps.py`, after `get_current_identity`:

```python
import httpx


async def get_vendor_http_client(request: Request) -> httpx.AsyncClient | None:
    """None in production (packages.contracts.vendor_api.list_vendor_offers
    opens and closes its own client per call, same as every other caller of
    that function) -- overridden in tests via
    app.dependency_overrides[get_vendor_http_client] to point at an
    in-process vendor app through httpx.ASGITransport, exactly like
    tests/contract/test_tender_vendor_contract.py already does for
    list_vendor_offers directly."""
    return getattr(request.app.state, "vendor_http_client", None)
```
(Add `import httpx` at the top of the file alongside the existing imports.)

Create `apps/api_tender/routers/decision.py`:

```python
"""Decision Core (Phase 4, task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1):
Go/No-Go and Bid/No-Bid/Conditional Bid. Human authority is final and
exclusive (ADR-0005) -- this router never computes or phrases a verdict
itself, only the one real derived signal (packages/decision/bid_readiness.py)
and structured storage for human-entered qualitative inputs and the
human's own decision.

GET /bid-readiness-candidate is the first place in this codebase that
calls match_boq_line/summarize_boq_matches against a real persisted
tender's BOQ lines and a real (paginated) vendor-offer fetch -- task 3.D's
final review flagged this end-to-end wiring as a real, deferred gap; this
router closes it.

data_realm is hardcoded to "vendor-sandbox" -- the only realm with any
data today (ADR-0004, synthetic-only until a legal gate). Revisit once
vendor-production data exists (docs/decisions/OPEN-QUESTIONS.md)."""

from __future__ import annotations

from datetime import datetime, timezone

import httpx
from fastapi import APIRouter, Depends, Header, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.contracts.vendor_api import VendorApiError, list_vendor_offers
from packages.decision.bid_readiness import build_bid_readiness_candidate
from packages.decision.decision_model import DECISION_TYPES, Decision, GoNoGoInputs
from packages.decision.decision_store import (
    load_bid_readiness_candidate,
    store_bid_readiness_candidate,
    store_decision,
    store_go_no_go_inputs,
    store_lock_in_requirement,
)
from packages.platform.errors import ApiError
from packages.platform.idempotency import IdempotencyKeyReused, IdempotencyStore, fingerprint
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity
from packages.tender.boq_lines_store import list_boq_lines_by_tender_version
from packages.tender.normalized import get_current_tender_version_id

from ..deps import get_connection, get_current_identity, get_vendor_http_client

router = APIRouter(prefix="/tenders/{tender_id}", tags=["decision"])

_idempotency_store = IdempotencyStore()


class GoNoGoInputsRequest(BaseModel):
    company_profile_notes: str
    qualification_notes: str
    financing_notes: str
    customer_reputation_notes: str
    pre_designated_winner_suspected: bool


class GoNoGoInputsResponse(BaseModel):
    id: int
    tender_id: int
    company_profile_notes: str
    qualification_notes: str
    financing_notes: str
    customer_reputation_notes: str
    pre_designated_winner_suspected: bool
    entered_by: str
    entered_at: datetime


class CriticalLineResponse(BaseModel):
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str


class BidReadinessCandidateResponse(BaseModel):
    id: int
    tender_id: int
    green_amount: str
    yellow_amount: str
    red_amount: str
    unpriced_line_count: int
    non_matchable_line_count: int
    non_matchable_amount: str
    total_priced_amount: str
    green_pct: float
    yellow_pct: float
    red_pct: float
    is_lottery: bool
    critical_lines: list[CriticalLineResponse]
    computed_at: datetime


class DecisionRequest(BaseModel):
    decision_type: str
    conditions: list[str]
    deadline: datetime | None = None
    justification: str
    go_no_go_inputs_id: int | None = None
    bid_readiness_candidate_id: int | None = None


class LockInRequirementResponse(BaseModel):
    id: int
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str
    status: str


class DecisionResponse(BaseModel):
    id: int
    tender_id: int
    decision_type: str
    conditions: list[str]
    deadline: datetime | None
    justification: str
    actor: str
    decided_at: datetime
    lock_in_requirements: list[LockInRequirementResponse]


@router.post("/go-no-go-inputs", response_model=GoNoGoInputsResponse, status_code=201)
async def create_go_no_go_inputs(
    tender_id: int,
    body: GoNoGoInputsRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.go_no_go.create", get_current_identity)),
) -> GoNoGoInputsResponse:
    route = "POST /tenders/{tender_id}/go-no-go-inputs"
    request_fingerprint = fingerprint({"tender_id": tender_id, **body.model_dump()})
    try:
        existing = await _idempotency_store.reserve(conn, idempotency_key, route, request_fingerprint)
    except IdempotencyKeyReused as exc:
        raise ApiError(status_code=409, code="idempotency_key_reused", message=str(exc)) from exc
    if existing is not None:
        return GoNoGoInputsResponse(**existing.response_body)

    entered_at = datetime.now(timezone.utc).isoformat()
    inputs = GoNoGoInputs(
        tender_id=tender_id,
        company_profile_notes=body.company_profile_notes,
        qualification_notes=body.qualification_notes,
        financing_notes=body.financing_notes,
        customer_reputation_notes=body.customer_reputation_notes,
        pre_designated_winner_suspected=body.pre_designated_winner_suspected,
        entered_by=identity.subject,
        entered_at=entered_at,
    )
    inputs_id = await store_go_no_go_inputs(conn, inputs)
    response = GoNoGoInputsResponse(
        id=inputs_id,
        tender_id=tender_id,
        company_profile_notes=inputs.company_profile_notes,
        qualification_notes=inputs.qualification_notes,
        financing_notes=inputs.financing_notes,
        customer_reputation_notes=inputs.customer_reputation_notes,
        pre_designated_winner_suspected=inputs.pre_designated_winner_suspected,
        entered_by=inputs.entered_by,
        entered_at=inputs.entered_at,
    )
    await _idempotency_store.store_response(conn, idempotency_key, route, 201, response.model_dump(mode="json"))
    return response


@router.get("/bid-readiness-candidate", response_model=BidReadinessCandidateResponse)
async def get_bid_readiness_candidate(
    tender_id: int,
    as_of: datetime,
    request: Request,
    conn: AsyncConnection = Depends(get_connection),
    vendor_http_client: httpx.AsyncClient | None = Depends(get_vendor_http_client),
    identity: Identity = Depends(require_permission("decision.bid_readiness.read", get_current_identity)),
) -> BidReadinessCandidateResponse:
    tender_version_id = await get_current_tender_version_id(conn, tender_id=tender_id)
    if tender_version_id is None:
        raise ApiError(status_code=404, code="not_found", message=f"tender {tender_id} not found or has no version")

    boq_lines = await list_boq_lines_by_tender_version(conn, tender_version_id=tender_version_id)
    if not boq_lines:
        raise ApiError(status_code=404, code="not_found", message=f"tender {tender_id} has no BOQ lines")

    settings = request.app.state.settings
    try:
        offers = await list_vendor_offers(
            settings.vendor_service_base_url,
            data_realm="vendor-sandbox",
            as_of=as_of.isoformat(),
            client=vendor_http_client,
        )
    except VendorApiError as exc:
        raise ApiError(status_code=502, code="vendor_service_unavailable", message=str(exc)) from exc

    candidate = build_bid_readiness_candidate(
        tender_id, boq_lines, offers, as_of=as_of, computed_at=datetime.now(timezone.utc).isoformat()
    )
    candidate_id = await store_bid_readiness_candidate(conn, candidate)
    return BidReadinessCandidateResponse(
        id=candidate_id,
        tender_id=candidate.tender_id,
        green_amount=str(candidate.summary.green_amount),
        yellow_amount=str(candidate.summary.yellow_amount),
        red_amount=str(candidate.summary.red_amount),
        unpriced_line_count=candidate.summary.unpriced_line_count,
        non_matchable_line_count=candidate.summary.non_matchable_line_count,
        non_matchable_amount=str(candidate.summary.non_matchable_amount),
        total_priced_amount=str(candidate.summary.total_priced_amount),
        green_pct=candidate.summary.green_pct,
        yellow_pct=candidate.summary.yellow_pct,
        red_pct=candidate.summary.red_pct,
        is_lottery=candidate.is_lottery,
        critical_lines=[CriticalLineResponse(**cl.__dict__) for cl in candidate.critical_lines],
        computed_at=candidate.computed_at,
    )


@router.post("/decisions", response_model=DecisionResponse, status_code=201)
async def create_decision(
    tender_id: int,
    body: DecisionRequest,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.decisions.create", get_current_identity)),
) -> DecisionResponse:
    if body.decision_type not in DECISION_TYPES:
        raise ApiError(
            status_code=422, code="unknown_decision_type", message=f"unknown decision_type: {body.decision_type}"
        )

    route = "POST /tenders/{tender_id}/decisions"
    request_fingerprint = fingerprint({"tender_id": tender_id, **body.model_dump(mode="json")})
    try:
        existing = await _idempotency_store.reserve(conn, idempotency_key, route, request_fingerprint)
    except IdempotencyKeyReused as exc:
        raise ApiError(status_code=409, code="idempotency_key_reused", message=str(exc)) from exc
    if existing is not None:
        return DecisionResponse(**existing.response_body)

    decided_at = datetime.now(timezone.utc).isoformat()
    decision = Decision(
        tender_id=tender_id,
        decision_type=body.decision_type,
        conditions=tuple(body.conditions),
        deadline=body.deadline.isoformat() if body.deadline else None,
        justification=body.justification,
        actor=identity.subject,
        decided_at=decided_at,
        go_no_go_inputs_id=body.go_no_go_inputs_id,
        bid_readiness_candidate_id=body.bid_readiness_candidate_id,
    )
    decision_id = await store_decision(conn, decision)

    lock_ins: list[LockInRequirementResponse] = []
    if body.decision_type in ("bid", "conditional_bid") and body.bid_readiness_candidate_id is not None:
        candidate_row = await load_bid_readiness_candidate(conn, body.bid_readiness_candidate_id)
        for line in candidate_row["critical_lines"]:
            lock_in_id = await store_lock_in_requirement(
                conn,
                tender_id=tender_id,
                decision_id=decision_id,
                boqline_source_line_id=line["boqline_source_line_id"],
                vendor_id=line["vendor_id"],
                vendor_name=line["vendor_name"],
            )
            lock_ins.append(
                LockInRequirementResponse(
                    id=lock_in_id,
                    boqline_source_line_id=line["boqline_source_line_id"],
                    vendor_id=line["vendor_id"],
                    vendor_name=line["vendor_name"],
                    status="pending",
                )
            )

    response = DecisionResponse(
        id=decision_id,
        tender_id=tender_id,
        decision_type=decision.decision_type,
        conditions=list(decision.conditions),
        deadline=decision.deadline,
        justification=decision.justification,
        actor=decision.actor,
        decided_at=decision.decided_at,
        lock_in_requirements=lock_ins,
    )
    await _idempotency_store.store_response(conn, idempotency_key, route, 201, response.model_dump(mode="json"))
    return response
```

In `packages/platform/settings.py`, add (after `trusted_proxy_cidrs`):
```python
    # Base URL of the Vendor service (ADR-0006: separate deployable process).
    # No default -- unlike DATABASE_URL, there is no universally-correct
    # local default port convention for this cross-service call the way
    # Postgres's 5432 is; an unset value should fail loudly the first time
    # something actually tries to reach the vendor service, not silently
    # point at a guessed URL (AGENTS.md hard ban #3).
    vendor_service_base_url: str = field(default_factory=lambda: os.environ.get("VENDOR_SERVICE_BASE_URL", ""))
```

In `apps/api_tender/main.py`, add `decision` to the router import and registration:
```python
from .routers import admin_users, decision, health
```
```python
    app.include_router(decision.router)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_decision_api_routes_exist.py -q`
Expected: PASS (all three routes now return non-404 — likely 401 unauthenticated or 422, which is fine; the test only proves the route exists).

Also run the full existing suite to confirm nothing broke:
```bash
python -m pytest tests/unit tests/integration -q -m "not live_network" --deselect tests/security/test_worldbank_live_fetch.py::test_live_fetch_against_real_worldbank_api
```

- [ ] **Step 5: Delete the superseded smoke-check file and commit**

Task 5 replaces `tests/integration/test_decision_api_routes_exist.py` with a full behavioral test file. Delete it now that Task 5's file will supersede it (do this in Task 5's own steps, not here — for this task's commit, keep the smoke-check file since Task 5 hasn't been written yet):

```bash
git add apps/api_tender/deps.py apps/api_tender/main.py apps/api_tender/routers/decision.py packages/platform/settings.py tests/integration/test_decision_api_routes_exist.py
git commit -m "feat(api-tender): Decision Core routes -- go-no-go-inputs, live bid-readiness-candidate, decisions (task 4.A)"
```

---

### Task 5: Full behavioral integration tests (RBAC, idempotency, live vendor fetch, lock-in generation)

**Files:**
- Create: `tests/integration/test_decision_api.py`
- Delete: `tests/integration/test_decision_api_routes_exist.py` (superseded)

**Interfaces:**
- Consumes: everything from Tasks 1-4, plus `apps.api_vendor.main.create_app` (to run a real in-process vendor app for the live bid-readiness call, same pattern as `tests/contract/test_tender_vendor_contract.py`), `packages.vendor.{vendor_model, vendor_store}` (to seed a real offer).
- Produces: nothing consumed by a later task — this is the plan's test-completeness gate.

- [ ] **Step 1: Write the failing tests**

Create `tests/integration/test_decision_api.py`:

```python
"""End-to-end over real HTTP for task 4.A's Decision Core routes: RBAC
deny-by-default, idempotency, a live bid-readiness-candidate computation
against a real in-process Vendor service (httpx.ASGITransport, same
pattern as tests/contract/test_tender_vendor_contract.py), and INV-20's
lock-in generation on a Bid decision."""

from __future__ import annotations

from decimal import Decimal

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from apps.api_vendor.main import create_app as create_vendor_app
from packages.platform.settings import Settings
from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import store_raw_snapshot
from packages.vendor.vendor_model import Offer, Vendor
from packages.vendor.vendor_store import store_offer, store_vendor

DECISION_PERMISSIONS = (
    "decision.go_no_go.create",
    "decision.bid_readiness.read",
    "decision.decisions.create",
)


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=14)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=14)
    app = create_vendor_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def client(tender_app, vendor_app):
    vendor_transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    vendor_client = httpx.AsyncClient(transport=vendor_transport, base_url="http://vendor-test")
    tender_app.state.vendor_http_client = vendor_client
    tender_app.state.settings = Settings(
        database_url=tender_app.state.settings.database_url,
        expected_schema_version=14,
        vendor_service_base_url="http://vendor-test",
    )
    tender_transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tender_transport, base_url="http://tender-test") as c:
        yield c
    await vendor_client.aclose()


@pytest_asyncio.fixture
async def pm_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('pm') RETURNING id"))).scalar()
        for perm in DECISION_PERMISSIONS:
            perm_id = (
                await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('pm-1', 'PM One', :r)"), {"r": role_id}
        )
    return "pm-1"


@pytest_asyncio.fixture
async def tender_with_boq(engine):
    line = BoqLine(
        source_line_id=1,
        page_number=1,
        section=None,
        category_code=None,
        description="Supply of rebar-12mm reinforcement steel",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )
    async with engine.begin() as conn:
        raw_snapshot_id = await store_raw_snapshot(
            conn,
            source="etender",
            resource_type="event_details",
            identity_key="test-decision-api-tender",
            body={"eventId": 42},
            contract_version="v1",
            correlation_id="test-decision-api",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-decision-api-tender")
        version_id = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=raw_snapshot_id, parser_version="v1", normalized_fields={}
        )
        await store_boq_lines(
            conn, source="etender", event_id=42, tender_version_id=version_id, raw_snapshot_id=raw_snapshot_id, lines=[line]
        )
    return tender_id


@pytest_asyncio.fixture
async def two_strong_vendors(engine):
    async with engine.begin() as conn:
        for name, seed in [("Vendor A", 1), ("Vendor B", 2)]:
            vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name=name, provider_type="synthetic", seed=seed)
            vendor_id, _api_key = await store_vendor(conn, vendor)
            offer = Offer(
                vendor_name=name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="rebar-12mm",
                price=850.0,
                currency="AZN",
                vat_rate=18.0,
                uom="t",
                uom_canonical_qty=1.0,
                moq=1.0,
                capacity=100.0,
                inventory=50.0,
                valid_from="2026-08-01T00:00:00+00:00",
                valid_until="2026-09-01T00:00:00+00:00",
                evidence_source="test",
                observed_at="2026-08-01T00:00:00+00:00",
                adverse_case=None,
                executable_status="reserved",
            )
            await store_offer(conn, vendor_id, offer)


async def test_go_no_go_inputs_requires_auth(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json={
            "company_profile_notes": "x",
            "qualification_notes": "x",
            "financing_notes": "x",
            "customer_reputation_notes": "x",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k1"},
    )
    assert response.status_code == 401


async def test_go_no_go_inputs_creates_a_record(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/go-no-go-inputs",
        json={
            "company_profile_notes": "20 years in market",
            "qualification_notes": "licenses current",
            "financing_notes": "bond available",
            "customer_reputation_notes": "pays on time",
            "pre_designated_winner_suspected": False,
        },
        headers={"Idempotency-Key": "k1", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["tender_id"] == tender_with_boq
    assert body["entered_by"] == "pm-1"


async def test_bid_readiness_candidate_computes_live_against_real_vendor_service(
    client, pm_user, tender_with_boq, two_strong_vendors
):
    response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["green_pct"] == 100.0
    assert body["is_lottery"] is False
    # Two strong vendors on the one BOQ line -- not single-vendor-critical.
    assert body["critical_lines"] == []


async def test_bid_readiness_candidate_flags_single_vendor_line_as_critical(client, pm_user, tender_with_boq, engine):
    async with engine.begin() as conn:
        vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Sole Vendor", provider_type="synthetic", seed=9)
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Sole Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="rebar-12mm",
            price=850.0,
            currency="AZN",
            vat_rate=18.0,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=100.0,
            inventory=50.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-01T00:00:00+00:00",
            adverse_case=None,
            executable_status="reserved",
        )
        await store_offer(conn, vendor_id, offer)

    response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["critical_lines"]) == 1
    assert body["critical_lines"][0]["vendor_name"] == "Sole Vendor"


async def test_decision_with_bid_generates_lock_in_requirements(client, pm_user, tender_with_boq, engine):
    async with engine.begin() as conn:
        vendor = Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Sole Vendor", provider_type="synthetic", seed=9)
        vendor_id, _api_key = await store_vendor(conn, vendor)
        offer = Offer(
            vendor_name="Sole Vendor",
            data_realm="vendor-sandbox",
            watermark="SYNTHETIC",
            material="rebar-12mm",
            price=850.0,
            currency="AZN",
            vat_rate=18.0,
            uom="t",
            uom_canonical_qty=1.0,
            moq=1.0,
            capacity=100.0,
            inventory=50.0,
            valid_from="2026-08-01T00:00:00+00:00",
            valid_until="2026-09-01T00:00:00+00:00",
            evidence_source="test",
            observed_at="2026-08-01T00:00:00+00:00",
            adverse_case=None,
            executable_status="reserved",
        )
        await store_offer(conn, vendor_id, offer)

    candidate_response = await client.get(
        f"/tenders/{tender_with_boq}/bid-readiness-candidate",
        params={"as_of": "2026-08-08T00:00:00Z"},
        headers={"X-Dev-User": "pm-1"},
    )
    candidate_id = candidate_response.json()["id"]

    decision_response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={
            "decision_type": "bid",
            "conditions": [],
            "justification": "full coverage, single vendor accepted",
            "bid_readiness_candidate_id": candidate_id,
        },
        headers={"Idempotency-Key": "k-decision-1", "X-Dev-User": "pm-1"},
    )

    assert decision_response.status_code == 201
    body = decision_response.json()
    assert body["decision_type"] == "bid"
    assert len(body["lock_in_requirements"]) == 1
    assert body["lock_in_requirements"][0]["vendor_name"] == "Sole Vendor"
    assert body["lock_in_requirements"][0]["status"] == "pending"


async def test_decision_rejects_unknown_decision_type(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={"decision_type": "maybe", "conditions": [], "justification": "x"},
        headers={"Idempotency-Key": "k-decision-2", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 422


async def test_decision_without_bid_type_does_not_generate_lock_ins(client, pm_user, tender_with_boq):
    response = await client.post(
        f"/tenders/{tender_with_boq}/decisions",
        json={"decision_type": "no_go", "conditions": [], "justification": "qualification stop"},
        headers={"Idempotency-Key": "k-decision-3", "X-Dev-User": "pm-1"},
    )
    assert response.status_code == 201
    assert response.json()["lock_in_requirements"] == []
```

Delete the superseded smoke-check file:
```bash
git rm tests/integration/test_decision_api_routes_exist.py
```

- [ ] **Step 2: Run tests to verify they fail or pass appropriately**

Run: `python -m pytest tests/integration/test_decision_api.py -q`
Expected: at this point (Task 4 already implemented the routes), most tests should PASS already — this task is primarily about *proving* the behavior thoroughly, not implementing new production code. If any test fails, read the failure carefully: it likely means one of Task 4's assumptions (fixture field names, response shapes) needs a small correction in `apps/api_tender/routers/decision.py`, not a new feature. Fix forward in this task's own commit.

- [ ] **Step 3: Run the full suite to confirm no regressions**

```bash
python -m pytest tests/ -q -m "not live_network" --deselect tests/security/test_worldbank_live_fetch.py::test_live_fetch_against_real_worldbank_api
```
Expected: all pass, including every pre-existing test.

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_decision_api.py
git commit -m "test(decision): full behavioral coverage for Decision Core routes -- RBAC, live vendor fetch, lock-in generation (task 4.A)"
```

---

### Task 6: Record deferred scope, run the full gate, update WORKLOG

**Files:**
- Modify: `docs/decisions/OPEN-QUESTIONS.md`
- Modify: `docs/reports/WORKLOG.md`

**Interfaces:**
- Consumes: nothing new — this task documents and verifies Tasks 1-5's combined result.
- Produces: nothing consumed by a later task.

- [ ] **Step 1: Append a new dated entry to `docs/decisions/OPEN-QUESTIONS.md`**

Append after the most recent entry:

```markdown

## 2026-08-08 — Task 4.A Decision Core scope

**Context:** Task 4.A (`TENDER_INTELLIGENCE_SPEC.md` §7.1, Decision Core: Go/No-Go → Bid), first task of Phase 4, started on owner GO per the Exit gate Phase 3 record above.

**Deviation/assumption:** Per an explicit owner decision recorded in this session's conversation (not previously in any document): Go/No-Go's qualitative inputs — company profile, qualification, financing, customer reputation, pre-designated-winner suspicion — are captured as **human-entered free text**, not computed. No source document supplies a scoring/weighting formula for any of these, and customer reputation specifically depends on Phase 4.C's Execution Ledger, which does not exist yet. This task only gives the human's own assessment a durable, queryable home (`go_no_go_inputs` table) — it does not attempt to derive or validate a Go/No-Go verdict from that text.

Five further gaps recorded, not silently approximated:
1. **Margin, risk concentration, own-resource-loading** (§7.1's other Bid/No-Bid criteria) are not computed — no source document supplies the company's own cost basis or resource schedule any of these need.
2. **P316's "three probabilities"** are not produced — no calibrated probability source exists; DFE's own `forecast_card.py` already defers this same gap (P311).
3. **INV-20's lock-in is only the identification half** — `lock_in_requirements` flags which BOQ lines need a lock-in and for which vendor, but does not generate an actual LOI/pre-order legal document.
4. **INV-06's No-Go override maker/checker flow** is not built — `no_go` exists as one of five `Decision` types, but a distinct, audited *override* flow for reversing an active No-Go is separate, future scope.
5. **`GET /bid-readiness-candidate` hardcodes `data_realm="vendor-sandbox"`** — the only realm with any data today (ADR-0004). Revisit once `vendor-production` data exists.

**Source conflict (if any):** None.

**Owner follow-up needed:** Yes, non-blocking. Items 1-2 need either real historical cost/resource data or an owner research/approval gate before they can be computed without inventing a number — same discipline as `D-VND-REP`. Items 3-4 are scoped, schedulable follow-up tasks, not open research questions. Item 5 resolves automatically once real vendor onboarding (Phase 7) exists.
```

- [ ] **Step 2: Run the full local gate**

```bash
python -m ruff format --check .
python -m ruff check .
python -m mypy packages apps
python tools/check_v1_untouched.py
python -m pytest tests/ -q -m "not live_network" --deselect tests/security/test_worldbank_live_fetch.py::test_live_fetch_against_real_worldbank_api
```
Expected: all clean/PASS. If `ruff format` needs changes, run `python -m ruff format .` and re-check. Fix any real `mypy` error in place.

- [ ] **Step 3: Append the WORKLOG entry**

Read the two most recent entries in `docs/reports/WORKLOG.md` first to match tone/format exactly, then append:

```markdown

## 2026-08-08 — Задание: Phase 4, задача 4.A (Decision Core)

**Сделано:**
- `packages/decision/matching.py::is_strong_source` — публичный (был `_is_strong_source`), переиспользуется задачей 4.A для определения критических по единственному вендору строк BOQ.
- `packages/tender/boq_lines_store.py::list_boq_lines_by_tender_version()` + `packages/tender/normalized.py::get_current_tender_version_id()` — первый реальный путь от `tenders.id` к персистентным `BoqLine` без ручной сборки source/event_id на каждом вызывающем месте.
- `packages/decision/decision_model.py` — `GoNoGoInputs` (человек вводит вручную: профиль компании, квалификация, финансирование, репутация заказчика, подозрение на «нарисованный» тендер — ни один автоматически не вычисляется, обоснование в OPEN-QUESTIONS), `Decision` (append-only, пять типов `go`/`no_go`/`bid`/`no_bid`/`conditional_bid`, `__post_init__` бросает на неизвестном типе), `LockInRequirement`.
- `packages/decision/bid_readiness.py::build_bid_readiness_candidate()` — единственный реально вычисляемый сигнал Bid/No-Bid: покрытие BOQ деньгами (`green_pct+yellow_pct` из уже существующего `boq_summary.py`) против порога `~85%` из самой спецификации (`LOTTERY_COVERAGE_THRESHOLD_PCT`), и строки, зависящие от единственного «сильного» (`is_strong_source`) вендора.
- Migration `0014_decision_core.sql` (schema version 13→14) + `packages/decision/decision_store.py` — персистентность всех четырёх новых сущностей, `decisions` без единого UPDATE/DELETE.
- `apps/api_tender/routers/decision.py` — три маршрута под `/tenders/{tender_id}` (`go-no-go-inputs`, `bid-readiness-candidate`, `decisions`), RBAC deny-by-default + idempotency-key на обеих мутациях (тот же паттерн, что `admin_users.py`). `GET /bid-readiness-candidate` — первое место во всём кодовой базе, где `match_boq_line`/`summarize_boq_matches` реально вызываются против персистентных BOQ-строк тендера и настоящего (постраничного) запроса к Vendor-сервису — задача 3.D's финальный ревью зафиксировал именно этот разрыв как реальный, но отложенный; здесь он закрыт. `POST /decisions` на типе `bid`/`conditional_bid` автоматически создаёт `LockInRequirement` по каждой критической строке из привязанного `BidReadinessCandidate` (INV-20's половина «идентификации», не «генерации LOI-документа»).
- **Осознанно не построено, зафиксировано, не замолчано:** маржа/концентрация риска/загрузка ресурсов (нет источника себестоимости), P316's «три вероятности» (нет калиброванного источника, тот же пробел уже есть в DFE's `forecast_card.py`), настоящая генерация LOI-документа (только флагирование), INV-06's maker/checker поток отмены No-Go, хардкод `data_realm="vendor-sandbox"` в live-эндпоинте — все в `docs/decisions/OPEN-QUESTIONS.md`, 2026-08-08.

**Вывод полного прогона (Fast+Full gate):**
```
$ python -m pytest tests/ -q -m "not live_network" --deselect tests/security/test_worldbank_live_fetch.py::test_live_fetch_against_real_worldbank_api
<paste actual output here after running Step 2>
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
<paste actual output here after running Step 2>
```

**Дальше:** Decision Core's human-authority-exclusive skeleton is real and proven end-to-end (live BOQ↔vendor fetch → candidate → human decision → lock-in flagging). Natural next Phase 4 work per `TENDER_INTELLIGENCE_SPEC.md` §7: task 4.B (post-submission tracking) or 4.C (Execution Ledger — which would also finally unblock this task's deferred customer-reputation gap).

**Блокеры:** нет новых. The five recorded gaps above are non-blocking, same discipline as every prior phase's deferred items.
```

Replace the `<paste actual output here...>` placeholders with the real command output from Step 2 before committing.

- [ ] **Step 4: Commit**

```bash
git add docs/decisions/OPEN-QUESTIONS.md docs/reports/WORKLOG.md
git commit -m "docs(decision): record task 4.A scope and deferred gaps, close out WORKLOG entry"
```

---

## Self-Review Notes

- **Spec coverage:** §7.1's Go/No-Go inputs → Task 2's `GoNoGoInputs` (human-entered, per owner decision). §7.1's Bid/No-Bid coverage rule + single-vendor-critical-line rule → Task 2's `bid_readiness.py`. §8's `Decision` entity → Task 2's `Decision` dataclass + Task 3's append-only store. INV-20's lock-in → Task 3's `lock_in_requirements` table + Task 4's auto-generation on a Bid/Conditional-Bid decision. ADR-0005's human-authority-exclusive rule → no endpoint ever computes/returns a verdict, only facts (`BidReadinessCandidate`) and the human's own recorded `Decision`. ADR-0001's one-authoritative-entity rule → every new table references real `tenders.id`, never a shadow tender identifier.
- **Placeholder scan:** no `TODO`/`TBD` in code; Task 6's two `<paste actual output here>` are explicit instructions to the implementer, not left-in-place placeholders in committed code.
- **Type consistency:** `tender_id: int` is the same name/type across `GoNoGoInputs`, `Decision`, `BidReadinessCandidate`, `LockInRequirement`, the router's path parameter, and every store function. `BidReadinessCandidate.critical_lines` (tuple of `CriticalLine`) ↔ the DB's `critical_lines` JSONB (list of dicts with the same three keys) ↔ `CriticalLineResponse`'s three fields — verified consistent across Tasks 2/3/4.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-08-08-phase4-task4a-decision-core.md`. Two execution options:

**1. Subagent-Driven (recommended)** - I dispatch a fresh subagent per task, review between tasks, fast iteration

**2. Inline Execution** - Execute tasks in this session using executing-plans, batch execution with checkpoints

**Which approach?**
