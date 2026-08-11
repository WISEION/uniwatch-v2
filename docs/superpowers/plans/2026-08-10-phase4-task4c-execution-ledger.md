# Phase 4, Task 4.C — Execution Ledger (EL) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Capture plan-vs-fact reality from the construction site for an already-decided (`bid`/`conditional_bid`) tender — via the same zero-entry-threshold ("napkin") input INV-18 already established for vendor pricing — and turn it into (1) a per-BOQ-line plan/fact delta, (2) a vendor reputation feed, and (3) a queryable buyer/customer execution history, per `TENDER_INTELLIGENCE_SPEC.md` §7.3, P318.

**Architecture:** A new `packages/decision` slice (Execution Ledger lives alongside Decision Core, not as a separate ADR-0006 service — EL needs in-process access to `packages/tender`'s `BoqLine`/BOQ data and `packages/decision`'s own `lock_in_requirements`, the same boundary `matching.py` already established for task 3.D). Raw napkin evidence (photo of a completion act, scanned invoice) is captured unconditionally first, then OCR'd into one or more `ExecutionFact` rows — each an atom of `tender_id → boqline_source_line_id? → planned_qty vs actual_qty → deviation_reason → culprit → observed_at`. "Planned" is never taken from the photo — it is looked up from this codebase's own already-stored BOQ line, so the plan side of the comparison is always authoritative, never a field-worker's guess. A vendor-culprit fact crosses the ADR-0006 service boundary through a new `packages/contracts/vendor_api.py` write call (mirroring the existing read-only `list_vendor_offers`) to append a `ReputationFact` in the Vendor service. Closing a project rolls its `ExecutionFact`s into a plan/fact summary and a coarse, unweighted overhead-buffer contribution (the actual cost-weighting formula is explicitly out of scope — Phase 4.D's calibration loop, not invented here).

**Tech Stack:** Same as the rest of the repo — Python 3.12, SQLAlchemy async + raw `text()` SQL, Postgres via testcontainers for integration tests, FastAPI for the new routes, the existing `packages/vendor`-proven Ollama OCR adapter (relocated, see Task 1).

## Global Constraints

- **Branch base:** this plan assumes `master` already includes task 4.B (migration `0015`, `expected_schema_version` default `"15"`) — confirmed merged 2026-08-10 (PR #21, commit `9b0ed94`). This worktree/branch is cut from that `master`, not stacked on the old 4.B branch.
- **Migration number is `0016`**, filename `migrations/0016_execution_ledger.sql`. Bump `packages/platform/settings.py`'s `expected_schema_version` default `"15"` → `"16"`. Grep first: `grep -rn "expected_schema_version=15" tests/` — every hit must be updated to `16` as part of Task 2's Step 4 (a stale hardcoded version fails `assert_schema_up_to_date()`), same discipline 4.B's own plan already called out for its own bump.
- **"Project" = the tender itself.** No source document defines a separate `Project` entity distinct from the awarded `Tender` (`TENDER_INTELLIGENCE_SPEC.md` §7.3's own language — "закрытый проект" — treats them as the same thing post-decision). `ExecutionFact.tender_id` **is** the `проект_ref` §8's data schema names — do not invent a new `projects` table.
- **`tender_id` (which project a capture belongs to) is supplied by the caller, never extracted by OCR.** Unlike `packages/vendor/napkin_provider.py` (where the vendor's own name is *in* the photographed price list), no source document supplies an algorithm for identifying which tender a construction-site photo belongs to from its pixels alone — the uploading channel/app already knows which site it's on. Only the BOQ *line* within that already-known tender is resolved from OCR text (Task 3), the same directional-substring-heuristic discipline `packages/decision/matching.py`'s `_material_matches` already established for offer-to-BOQ-line matching (no better algorithm exists yet — do not invent one here either).
- **Voice-note transcription (ASR) is still not a resolved tech choice** (`docs/decisions/OPEN-QUESTIONS.md`, same open gap task 3.A's napkin ingestion already recorded). `execution_napkin_evidence.capture_kind` accepts `'voice'` and stores the raw bytes unconditionally (INV-18: capture must never depend on whether the system currently understands it) but Task 5's route does **not** attempt to parse a `'voice'` capture — it returns `parsed: false` with the evidence id, never a guessed transcript.
- **Never invent a weighting/scoring formula.** `D-VND-REP` (the vendor trust-coefficient) is still open and out of scope here; this plan's vendor-reputation feed only appends typed `ReputationFact` rows (already unweighted booleans downstream, per `packages/vendor/reputation_store.py`), never a score. The "historical overhead buffer" (Task 7) is a **raw count per deviation category**, not a cost-weighted adjustment — the formula that turns it into an actual estimate overlay is Phase 4.D's calibration loop, explicitly not built here (`TENDER_INTELLIGENCE_SPEC.md` §7.4, P319).
- **Never invent a `ReputationFact.ttl_days` number for a real (non-synthetic) fact.** INV-17 explicitly names "квалификация бригады/репутация" as a TTL class whose exact number is **not resolved** (`TBD-TIS-01`, same regime as the PRD's `TBD-01`) — the only existing `ReputationFact` construction site (`packages/vendor/synthetic_reputation.py`) samples an arbitrary TTL, but that is fine only because it is explicitly `SYNTHETIC` demo data, not a template to copy for a fact stemming from a real field observation. Task 6's napkin route therefore takes `reputation_ttl_days` as an explicit, optional, no-default request field — a vendor-culprit fact with a mappable event_type but no supplied TTL is queued via `exception_queue` for a human to resolve, never posted with a guessed number (hard ban #3).
- **`deviation_category` is constrained to the four tokens §7.3 itself names** (`preliminaries`, `downtime`, `rework`, `last_mile` — "preliminaries, простои, переделки, последняя миля") — nullable; a real observation that doesn't cleanly fit one of these four stays `None`, never force-mapped.
- **`culprit_type` is constrained to `('vendor', 'customer', 'internal', 'external')`** — the two the spec explicitly names as feeding downstream systems (vendor → SCG reputation task 3.B; customer → Go/No-Go) plus `internal` (own crew/planning fault) and `external` (weather/force majeure) needed for an honest plan/fact record that isn't always somebody's fault.
- **`ExecutionFact`/`execution_napkin_evidence` are append-only** (ADR-0003 layer 2/3: derived signal from raw evidence) — no UPDATE/DELETE against either from application code, same discipline as `tender_change_events`/`boq_line_recalc_flags` (task 4.B).
- **The OCR engine adapter moves from `packages/vendor` to `packages/platform`** (Task 1) because a second domain (`packages/decision`, this task) now needs the identical `OcrEngine` Protocol, and `packages/decision` must never import `packages/vendor` directly for it (ADR-0001 domain boundary — the exact same reasoning `packages/vendor/napkin_evidence.py`'s own docstring already gives for *not* reusing `packages/tender/raw_snapshot.py`). `ocr_settings.py`'s prior docstring argued OCR was vendor-domain-specific config — that reasoning no longer holds once a second domain needs it; `packages/platform` is exactly "cross-cutting... shared LIBRARY" per this repo's own `CLAUDE.md`.
- **`/internal/reputation-facts` is deliberately unauthenticated**, same known, tracked gap as the existing `/internal/offers`/`/internal/ping` (ADR-0006's real service-to-service auth is deferred to the still-open `D-IDP`/`D-HOST` decisions, `docs/decisions/OPEN-QUESTIONS.md`) — inheriting an existing documented exposure, not introducing a new one.
- Every new DB-touching function takes `conn: AsyncConnection` as its first parameter (or second, after `vendor_id`-style positional args matching existing store conventions) and is `async def`, matching every existing store module in `packages/tender` and `packages/decision`.

---

### Task 1: Relocate the OCR engine adapter to `packages/platform`

**Files:**
- Move: `packages/vendor/ocr_engine.py` → `packages/platform/ocr_engine.py`
- Move: `packages/vendor/ollama_ocr_engine.py` → `packages/platform/ollama_ocr_engine.py`
- Move: `packages/vendor/ocr_settings.py` → `packages/platform/ocr_settings.py`
- Modify: `packages/vendor/napkin_provider.py` (import path only)
- Modify: `tests/unit/test_napkin_provider.py`, `tests/unit/test_ollama_ocr_engine.py` (import paths only)

**Interfaces:**
- Consumes: nothing new.
- Produces: `packages.platform.ocr_engine.OcrEngine` (Protocol), `OcrEngineError`; `packages.platform.ollama_ocr_engine.OllamaOcrEngine`; `packages.platform.ocr_settings.OcrSettings`, `get_ocr_settings()`. Identical shapes to today — a pure relocation, no signature changes. Task 4 (this plan) and `packages/vendor/napkin_provider.py` (unchanged behavior) both import from the new location.

- [ ] **Step 1: Move the three files with their content unchanged**

```bash
git mv packages/vendor/ocr_engine.py packages/platform/ocr_engine.py
git mv packages/vendor/ollama_ocr_engine.py packages/platform/ollama_ocr_engine.py
git mv packages/vendor/ocr_settings.py packages/platform/ocr_settings.py
```

In the moved `packages/platform/ocr_settings.py`, update the docstring's first paragraph (it currently argues the opposite of what is now true):

```python
"""OCR engine configuration. Lives in packages/platform (not a
vendor-domain package) because a second domain now needs the identical
OcrEngine Protocol -- packages/decision's Execution Ledger napkin
ingestion (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3) --
and packages/decision must never import packages/vendor directly
(ADR-0001 domain boundary). This is exactly the "cross-cutting...
shared LIBRARY" packages/platform already is for DATABASE_URL etc.
(CLAUDE.md), not domain scoring/business-decision logic itself.
```

(keep the remaining paragraphs about `ollama_base_url`/`ocr_model_name` defaults verbatim — only the first paragraph's rationale changes.)

- [ ] **Step 2: Update the two import sites**

In `packages/vendor/napkin_provider.py`, change:
```python
from .ocr_engine import OcrEngine
```
to:
```python
from packages.platform.ocr_engine import OcrEngine
```

In `tests/unit/test_napkin_provider.py`, change:
```python
from packages.vendor.ocr_engine import OcrEngine
```
to:
```python
from packages.platform.ocr_engine import OcrEngine
```

In `tests/unit/test_ollama_ocr_engine.py`, change:
```python
from packages.vendor.ocr_engine import OcrEngineError
from packages.vendor.ollama_ocr_engine import OllamaOcrEngine
```
to:
```python
from packages.platform.ocr_engine import OcrEngineError
from packages.platform.ollama_ocr_engine import OllamaOcrEngine
```

`packages/platform/ollama_ocr_engine.py`'s own `from .ocr_engine import OcrEngineError` stays a relative import unchanged — both files now live in the same package.

- [ ] **Step 3: Run tests to verify nothing broke**

Run: `python -m pytest tests/unit/test_napkin_provider.py tests/unit/test_ollama_ocr_engine.py -q`
Expected: all PASS (same tests, new import paths).
Run: `python -m ruff check packages/platform/ocr_engine.py packages/platform/ollama_ocr_engine.py packages/platform/ocr_settings.py packages/vendor/napkin_provider.py`
Expected: clean.

- [ ] **Step 4: Commit**

```bash
git add packages/platform/ocr_engine.py packages/platform/ollama_ocr_engine.py packages/platform/ocr_settings.py packages/vendor/napkin_provider.py tests/unit/test_napkin_provider.py tests/unit/test_ollama_ocr_engine.py
git commit -m "refactor(platform,vendor): relocate OCR engine adapter to packages/platform (task 4.C prep)"
```

---

### Task 2: Migration + `ExecutionFact` model + append-only stores

**Files:**
- Create: `migrations/0016_execution_ledger.sql`
- Create: `packages/decision/execution_fact_model.py`
- Create: `packages/decision/execution_napkin_evidence.py`
- Create: `packages/decision/execution_ledger_store.py`
- Modify: `packages/platform/settings.py` (`expected_schema_version` default `"15"` → `"16"`)
- Test: `tests/integration/test_execution_ledger_store.py`, `tests/integration/test_execution_napkin_evidence.py`, `tests/unit/test_execution_fact_model.py`

**Interfaces:**
- Consumes: `tenders` (existing).
- Produces:
  - `packages.decision.execution_fact_model.DEVIATION_CATEGORIES: tuple[str, ...]`, `CULPRIT_TYPES: tuple[str, ...]`, `ExecutionFact` (frozen dataclass: `tender_id: int`, `boqline_source_line_id: int | None`, `planned_qty: Decimal | None`, `actual_qty: Decimal | None`, `deviation_reason: str`, `deviation_category: str | None`, `culprit_type: str`, `culprit_vendor_name: str | None`, `culprit_vendor_id: int | None`, `evidence_source: str`, `observed_at: str`) — raises `ValueError` in `__post_init__` on an unknown `culprit_type`/`deviation_category`, or `culprit_vendor_name`/`culprit_vendor_id` set when `culprit_type != "vendor"`, or absent when `culprit_type == "vendor"`.
  - `packages.decision.execution_napkin_evidence.save_execution_napkin_evidence(conn, *, tender_id: int, capture_kind: str, raw_bytes: bytes, mime_type: str, correlation_id: str) -> int`, `get_execution_napkin_evidence(conn, evidence_id: int) -> ExecutionNapkinEvidence`.
  - `packages.decision.execution_ledger_store.store_execution_fact(conn, fact: ExecutionFact) -> int`, `list_execution_facts_by_tender(conn, *, tender_id: int) -> list[dict[str, Any]]`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_execution_fact_model.py
from __future__ import annotations

from decimal import Decimal

import pytest

from packages.decision.execution_fact_model import CULPRIT_TYPES, DEVIATION_CATEGORIES, ExecutionFact


def _fact(**overrides) -> ExecutionFact:
    defaults = dict(
        tender_id=1,
        boqline_source_line_id=501,
        planned_qty=Decimal("10"),
        actual_qty=Decimal("15"),
        deviation_reason="crane did not arrive, half-day idle",
        deviation_category="downtime",
        culprit_type="vendor",
        culprit_vendor_name="Acme Crane Co",
        culprit_vendor_id=42,
        evidence_source="napkin-ocr:1",
        observed_at="2026-08-10T00:00:00+00:00",
    )
    defaults.update(overrides)
    return ExecutionFact(**defaults)


def test_deviation_categories_are_exactly_the_four_spec_tokens():
    assert DEVIATION_CATEGORIES == ("preliminaries", "downtime", "rework", "last_mile")


def test_culprit_types_are_exactly_the_four_named_categories():
    assert CULPRIT_TYPES == ("vendor", "customer", "internal", "external")


def test_valid_vendor_culprit_fact_constructs():
    fact = _fact()
    assert fact.culprit_type == "vendor"


def test_valid_non_vendor_culprit_fact_constructs_without_vendor_fields():
    fact = _fact(culprit_type="customer", culprit_vendor_name=None, culprit_vendor_id=None)
    assert fact.culprit_type == "customer"


def test_unknown_culprit_type_raises():
    with pytest.raises(ValueError, match="culprit_type"):
        _fact(culprit_type="weather")


def test_unknown_deviation_category_raises():
    with pytest.raises(ValueError, match="deviation_category"):
        _fact(deviation_category="scope_creep")


def test_none_deviation_category_is_allowed():
    fact = _fact(deviation_category=None)
    assert fact.deviation_category is None


def test_vendor_culprit_without_vendor_name_raises():
    with pytest.raises(ValueError, match="culprit_vendor_name"):
        _fact(culprit_vendor_name=None)


def test_non_vendor_culprit_with_vendor_name_raises():
    with pytest.raises(ValueError, match="culprit_vendor_name"):
        _fact(culprit_type="customer", culprit_vendor_id=None)


def test_non_vendor_culprit_with_vendor_id_raises():
    with pytest.raises(ValueError, match="culprit_vendor_id"):
        _fact(culprit_type="internal", culprit_vendor_name=None)
```

```python
# tests/integration/test_execution_napkin_evidence.py
from __future__ import annotations

import pytest

from packages.decision.execution_napkin_evidence import get_execution_napkin_evidence, save_execution_napkin_evidence
from packages.tender.normalized import get_or_create_tender


async def test_save_and_get_roundtrips_raw_bytes(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-evidence-1")
        evidence_id = await save_execution_napkin_evidence(
            conn,
            tender_id=tender_id,
            capture_kind="photo",
            raw_bytes=b"fake-jpeg-bytes",
            mime_type="image/jpeg",
            correlation_id="test-4c-evidence-1",
        )
        evidence = await get_execution_napkin_evidence(conn, evidence_id)

    assert evidence.tender_id == tender_id
    assert evidence.capture_kind == "photo"
    assert evidence.raw_bytes == b"fake-jpeg-bytes"
    assert evidence.checksum == __import__("hashlib").sha256(b"fake-jpeg-bytes").hexdigest()


async def test_voice_capture_kind_is_accepted(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-evidence-2")
        evidence_id = await save_execution_napkin_evidence(
            conn,
            tender_id=tender_id,
            capture_kind="voice",
            raw_bytes=b"fake-audio-bytes",
            mime_type="audio/ogg",
            correlation_id="test-4c-evidence-2",
        )
        evidence = await get_execution_napkin_evidence(conn, evidence_id)
    assert evidence.capture_kind == "voice"


async def test_a_recapture_inserts_a_new_row_not_an_update(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-evidence-3")
        first_id = await save_execution_napkin_evidence(
            conn, tender_id=tender_id, capture_kind="photo", raw_bytes=b"v1", mime_type="image/jpeg", correlation_id="c1"
        )
        second_id = await save_execution_napkin_evidence(
            conn, tender_id=tender_id, capture_kind="photo", raw_bytes=b"v2", mime_type="image/jpeg", correlation_id="c2"
        )
    assert first_id != second_id
```

```python
# tests/integration/test_execution_ledger_store.py
from __future__ import annotations

from decimal import Decimal

from packages.decision.execution_fact_model import ExecutionFact
from packages.decision.execution_ledger_store import list_execution_facts_by_tender, store_execution_fact
from packages.tender.normalized import get_or_create_tender


def _fact(tender_id: int, **overrides) -> ExecutionFact:
    defaults = dict(
        tender_id=tender_id,
        boqline_source_line_id=501,
        planned_qty=Decimal("10"),
        actual_qty=Decimal("15"),
        deviation_reason="crane did not arrive, half-day idle",
        deviation_category="downtime",
        culprit_type="vendor",
        culprit_vendor_name="Acme Crane Co",
        culprit_vendor_id=42,
        evidence_source="napkin-ocr:1",
        observed_at="2026-08-10T00:00:00+00:00",
    )
    defaults.update(overrides)
    return ExecutionFact(**defaults)


async def test_store_and_list_a_fact(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-1")
        fact_id = await store_execution_fact(conn, _fact(tender_id))
        facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)

    assert len(facts) == 1
    assert facts[0]["id"] == fact_id
    assert facts[0]["boqline_source_line_id"] == 501
    assert facts[0]["planned_qty"] == Decimal("10")
    assert facts[0]["actual_qty"] == Decimal("15")
    assert facts[0]["culprit_vendor_id"] == 42


async def test_list_execution_facts_is_scoped_to_the_tender(engine):
    async with engine.begin() as conn:
        tender_a = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-2a")
        tender_b = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-2b")
        await store_execution_fact(conn, _fact(tender_a))

        facts_b = await list_execution_facts_by_tender(conn, tender_id=tender_b)
    assert facts_b == []


async def test_a_fact_with_no_boqline_reference_is_allowed(engine):
    # A site-wide observation (e.g. "preliminaries" overhead) is not tied to
    # any one priced BOQ line -- boqline_source_line_id must be nullable.
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-3")
        await store_execution_fact(
            conn,
            _fact(
                tender_id,
                boqline_source_line_id=None,
                planned_qty=None,
                actual_qty=None,
                culprit_type="internal",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                deviation_category="preliminaries",
            ),
        )
        facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)
    assert facts[0]["boqline_source_line_id"] is None
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_execution_fact_model.py -q` — expected FAIL (`ModuleNotFoundError`).
Run: `python -m pytest tests/integration/test_execution_napkin_evidence.py tests/integration/test_execution_ledger_store.py -q` — expected FAIL (`ModuleNotFoundError`, tables don't exist).

- [ ] **Step 3: Implement**

Create `migrations/0016_execution_ledger.sql`:

```sql
-- Execution Ledger (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3,
-- INV-18, P318): plan-vs-fact reality from the construction site for an
-- already-decided tender. execution_napkin_evidence and execution_facts are
-- both append-only (ADR-0003 layers 1/2-3) -- application code never issues
-- an UPDATE/DELETE against either.
--
-- "Project" == the tender itself (no separate Project entity exists or is
-- invented here) -- tender_id is Section8's proект_ref.

-- Raw immutable napkin-ingestion evidence, scoped to one tender (unlike
-- vendor_napkin_evidence, which isn't tied to any one tender). A separate
-- table from vendor_napkin_evidence: packages/decision must never share a
-- table with packages/vendor across the ADR-0001 domain boundary, and this
-- capture is inherently project-scoped from the moment it's taken.
CREATE TABLE execution_napkin_evidence (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    capture_kind TEXT NOT NULL CHECK (capture_kind IN ('photo', 'voice')),
    mime_type TEXT NOT NULL,
    checksum TEXT NOT NULL,
    raw_bytes BYTEA NOT NULL,
    correlation_id TEXT NOT NULL,
    captured_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX execution_napkin_evidence_tender_idx ON execution_napkin_evidence (tender_id);
CREATE INDEX execution_napkin_evidence_checksum_idx ON execution_napkin_evidence (checksum);

-- One atom: project -> position -> plan vs fact -> deviation reason ->
-- culprit -> date (Section7.3's own atom list). boqline_source_line_id is
-- nullable: a site-wide observation (e.g. preliminaries overhead) is not
-- tied to any one priced BOQ line. planned_qty/actual_qty are nullable for
-- the same reason -- not every deviation is a clean quantity comparison
-- (e.g. a pure downtime narrative has no qty at all).
CREATE TABLE execution_facts (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    boqline_source_line_id BIGINT,
    planned_qty NUMERIC,
    actual_qty NUMERIC,
    deviation_reason TEXT NOT NULL,
    deviation_category TEXT CHECK (deviation_category IN ('preliminaries', 'downtime', 'rework', 'last_mile')),
    culprit_type TEXT NOT NULL CHECK (culprit_type IN ('vendor', 'customer', 'internal', 'external')),
    culprit_vendor_name TEXT,
    culprit_vendor_id BIGINT,
    evidence_source TEXT NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX execution_facts_tender_idx ON execution_facts (tender_id);
```

In `packages/platform/settings.py`, change:
```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "15")))
```
to:
```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "16")))
```

Create `packages/decision/execution_fact_model.py`:

```python
"""Execution Ledger domain model (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md
Section7.3, Section8's ExecutionFact entity, ADR-0003 layers 1-3). Pure dataclass,
no DB -- packages/decision/execution_ledger_store.py persists these.

"Planned" always comes from this codebase's own stored BOQ line (never the
field-worker's photo/voice note) -- see execution_napkin_provider.py. This
module only guards that culprit_type/deviation_category are one of the
tokens TENDER_INTELLIGENCE_SPEC.md Section7.3 actually names, and that a
vendor culprit always carries a name (needed to later resolve a vendor_id,
Task 3) while a non-vendor culprit never carries vendor fields."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

DEVIATION_CATEGORIES = ("preliminaries", "downtime", "rework", "last_mile")
CULPRIT_TYPES = ("vendor", "customer", "internal", "external")


@dataclass(frozen=True)
class ExecutionFact:
    tender_id: int
    boqline_source_line_id: int | None
    planned_qty: Decimal | None
    actual_qty: Decimal | None
    deviation_reason: str
    deviation_category: str | None
    culprit_type: str
    culprit_vendor_name: str | None
    culprit_vendor_id: int | None
    evidence_source: str
    observed_at: str

    def __post_init__(self) -> None:
        if self.culprit_type not in CULPRIT_TYPES:
            raise ValueError(f"unknown culprit_type: {self.culprit_type!r}")
        if self.deviation_category is not None and self.deviation_category not in DEVIATION_CATEGORIES:
            raise ValueError(f"unknown deviation_category: {self.deviation_category!r}")
        if self.culprit_type == "vendor":
            if not self.culprit_vendor_name:
                raise ValueError("culprit_vendor_name is required when culprit_type is 'vendor'")
        else:
            if self.culprit_vendor_name is not None:
                raise ValueError("culprit_vendor_name must be None unless culprit_type is 'vendor'")
            if self.culprit_vendor_id is not None:
                raise ValueError("culprit_vendor_id must be None unless culprit_type is 'vendor'")
```

Create `packages/decision/execution_napkin_evidence.py`:

```python
"""Raw immutable execution-ledger napkin-ingestion evidence (Phase 4, task
4.C, INV-18, ADR-0003 layer 1). A re-capture always creates a new row;
application code never issues an UPDATE against execution_napkin_evidence.
checksum is sha256 of the exact raw bytes captured -- same provenance
discipline as packages/tender/raw_snapshot.py and
packages/vendor/napkin_evidence.py, kept as its own table (not a reuse of
either) because this is tender-scoped from capture time and packages/decision
must never share a table with packages/vendor across the ADR-0001 domain
boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ExecutionNapkinEvidence:
    id: int
    tender_id: int
    capture_kind: str
    mime_type: str
    checksum: str
    raw_bytes: bytes
    correlation_id: str


def checksum_of(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


async def save_execution_napkin_evidence(
    conn: AsyncConnection,
    *,
    tender_id: int,
    capture_kind: str,
    raw_bytes: bytes,
    mime_type: str,
    correlation_id: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO execution_napkin_evidence
                    (tender_id, capture_kind, mime_type, checksum, raw_bytes, correlation_id)
                VALUES (:tender_id, :capture_kind, :mime_type, :checksum, :raw_bytes, :correlation_id)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "capture_kind": capture_kind,
                "mime_type": mime_type,
                "checksum": checksum_of(raw_bytes),
                "raw_bytes": raw_bytes,
                "correlation_id": correlation_id,
            },
        )
    ).scalar_one()


async def get_execution_napkin_evidence(conn: AsyncConnection, evidence_id: int) -> ExecutionNapkinEvidence:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, capture_kind, mime_type, checksum, raw_bytes, correlation_id
                    FROM execution_napkin_evidence WHERE id = :id
                    """
                ),
                {"id": evidence_id},
            )
        )
        .mappings()
        .one()
    )
    return ExecutionNapkinEvidence(
        id=row["id"],
        tender_id=row["tender_id"],
        capture_kind=row["capture_kind"],
        mime_type=row["mime_type"],
        checksum=row["checksum"],
        raw_bytes=bytes(row["raw_bytes"]),
        correlation_id=row["correlation_id"],
    )
```

Create `packages/decision/execution_ledger_store.py`:

```python
"""Persistence for Execution Ledger facts (Phase 4, task 4.C,
TENDER_INTELLIGENCE_SPEC.md Section7.3, P318). execution_facts is append-only
(ADR-0003 layer 2/3) -- no UPDATE/DELETE against it from this module."""

from __future__ import annotations

from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .execution_fact_model import ExecutionFact


async def store_execution_fact(conn: AsyncConnection, fact: ExecutionFact) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO execution_facts
                    (tender_id, boqline_source_line_id, planned_qty, actual_qty, deviation_reason,
                     deviation_category, culprit_type, culprit_vendor_name, culprit_vendor_id,
                     evidence_source, observed_at)
                VALUES
                    (:tender_id, :boqline_source_line_id, :planned_qty, :actual_qty, :deviation_reason,
                     :deviation_category, :culprit_type, :culprit_vendor_name, :culprit_vendor_id,
                     :evidence_source, :observed_at)
                RETURNING id
                """
            ),
            {
                "tender_id": fact.tender_id,
                "boqline_source_line_id": fact.boqline_source_line_id,
                "planned_qty": fact.planned_qty,
                "actual_qty": fact.actual_qty,
                "deviation_reason": fact.deviation_reason,
                "deviation_category": fact.deviation_category,
                "culprit_type": fact.culprit_type,
                "culprit_vendor_name": fact.culprit_vendor_name,
                "culprit_vendor_id": fact.culprit_vendor_id,
                "evidence_source": fact.evidence_source,
                "observed_at": fact.observed_at,
            },
        )
    ).scalar_one()


async def list_execution_facts_by_tender(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, boqline_source_line_id, planned_qty, actual_qty, deviation_reason,
                           deviation_category, culprit_type, culprit_vendor_name, culprit_vendor_id,
                           evidence_source, observed_at
                    FROM execution_facts WHERE tender_id = :tender_id ORDER BY id
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

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_execution_fact_model.py tests/integration/test_execution_napkin_evidence.py tests/integration/test_execution_ledger_store.py -q`
Expected: all PASS.
Also run: `grep -rn "expected_schema_version=15" tests/` and update every hit to `16` (same requirement 4.B's own plan called out for its bump); then run `python -m pytest tests/ -q -m "not live_network"` to confirm nothing else regressed.

- [ ] **Step 5: Commit**

```bash
git add migrations/0016_execution_ledger.sql packages/platform/settings.py packages/decision/execution_fact_model.py packages/decision/execution_napkin_evidence.py packages/decision/execution_ledger_store.py tests/unit/test_execution_fact_model.py tests/integration/test_execution_napkin_evidence.py tests/integration/test_execution_ledger_store.py
# also add any test file touched to fix a hardcoded expected_schema_version=15
git commit -m "feat(decision): migration + ExecutionFact model and stores (task 4.C), schema version 15->16"
```

---

### Task 3: Pure resolution — matching free-text against known BOQ lines and locked-in vendors

**Files:**
- Create: `packages/decision/execution_fact_resolution.py`
- Test: `tests/unit/test_execution_fact_resolution.py`

**Interfaces:**
- Consumes: `packages.tender.boq_line_model.BoqLine` (existing), `list[dict[str, Any]]` shaped like `list_lock_in_requirements_by_tender`'s return value (existing, has `boqline_source_line_id`, `vendor_id`, `vendor_name` keys).
- Produces: `resolve_boqline_reference(boq_lines: list[BoqLine], line_description: str | None) -> BoqLine | None` — same directional, case-insensitive substring heuristic as `matching.py`'s `_material_matches` (description found inside `boq_line.description`, not the reverse), returns the first match or `None`. `resolve_vendor_reference(lock_ins: list[dict[str, Any]], culprit_vendor_name: str | None) -> int | None` — matches `culprit_vendor_name` case-insensitively against each lock-in's `vendor_name`, returns that lock-in's `vendor_id` or `None` if no match/name given.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_execution_fact_resolution.py
from __future__ import annotations

from decimal import Decimal

from packages.decision.execution_fact_resolution import resolve_boqline_reference, resolve_vendor_reference
from packages.tender.boq_line_model import BoqLine


def _line(source_line_id: int, description: str) -> BoqLine:
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
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )


def test_resolve_boqline_reference_matches_a_substring_case_insensitively():
    lines = [_line(1, "Rebar 12mm, grade B500B"), _line(2, "Concrete C25/30")]
    result = resolve_boqline_reference(lines, "rebar 12mm")
    assert result is not None
    assert result.source_line_id == 1


def test_resolve_boqline_reference_returns_none_when_no_match():
    lines = [_line(1, "Rebar 12mm")]
    assert resolve_boqline_reference(lines, "excavator rental") is None


def test_resolve_boqline_reference_returns_none_for_none_description():
    lines = [_line(1, "Rebar 12mm")]
    assert resolve_boqline_reference(lines, None) is None


def test_resolve_boqline_reference_returns_first_match_when_ambiguous():
    lines = [_line(1, "Rebar 12mm"), _line(2, "Rebar 12mm secondary batch")]
    result = resolve_boqline_reference(lines, "rebar 12mm")
    assert result is not None
    assert result.source_line_id == 1


def test_resolve_vendor_reference_matches_case_insensitively():
    lock_ins = [
        {"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"},
        {"boqline_source_line_id": 2, "vendor_id": 43, "vendor_name": "Beta Rebar Supply"},
    ]
    assert resolve_vendor_reference(lock_ins, "acme crane co") == 42


def test_resolve_vendor_reference_returns_none_when_no_match():
    lock_ins = [{"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"}]
    assert resolve_vendor_reference(lock_ins, "Unknown Supplier LLC") is None


def test_resolve_vendor_reference_returns_none_for_none_name():
    lock_ins = [{"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"}]
    assert resolve_vendor_reference(lock_ins, None) is None


def test_resolve_vendor_reference_returns_none_for_empty_lock_ins():
    assert resolve_vendor_reference([], "Acme Crane Co") is None
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/unit/test_execution_fact_resolution.py -q` — expected FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

Create `packages/decision/execution_fact_resolution.py`:

```python
"""Pure resolution of free-text napkin observations against this codebase's
own already-known BOQ lines and locked-in vendors (Phase 4, task 4.C).
"Planned" data must come from here, never from the photo/voice note itself
-- these functions are how execution_napkin_provider.py bridges OCR'd text
back to a specific boqline_source_line_id / vendor_id.

resolve_boqline_reference uses the same directional, case-insensitive
substring heuristic as matching.py's _material_matches (no better
entity-matching algorithm exists yet, same honest limitation)."""

from __future__ import annotations

from typing import Any

from packages.tender.boq_line_model import BoqLine


def resolve_boqline_reference(boq_lines: list[BoqLine], line_description: str | None) -> BoqLine | None:
    if not line_description:
        return None
    needle = line_description.strip().lower()
    if not needle:
        return None
    for line in boq_lines:
        if needle in line.description.lower():
            return line
    return None


def resolve_vendor_reference(lock_ins: list[dict[str, Any]], culprit_vendor_name: str | None) -> int | None:
    if not culprit_vendor_name:
        return None
    needle = culprit_vendor_name.strip().lower()
    if not needle:
        return None
    for lock_in in lock_ins:
        if lock_in["vendor_name"].strip().lower() == needle:
            return lock_in["vendor_id"]
    return None
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/unit/test_execution_fact_resolution.py -q` — expected PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/decision/execution_fact_resolution.py tests/unit/test_execution_fact_resolution.py
git commit -m "feat(decision): resolve napkin observations against known BOQ lines and locked-in vendors (task 4.C)"
```

---

### Task 4: Napkin provider — OCR extraction into draft `ExecutionFact`s

**Files:**
- Create: `packages/decision/execution_napkin_provider.py`
- Test: `tests/unit/test_execution_napkin_provider.py`

**Interfaces:**
- Consumes: `packages.platform.ocr_engine.OcrEngine` (Task 1), `packages.decision.execution_fact_model.ExecutionFact`/`DEVIATION_CATEGORIES`/`CULPRIT_TYPES` (Task 2), `packages.decision.execution_fact_resolution.resolve_boqline_reference`/`resolve_vendor_reference` (Task 3), `packages.tender.boq_line_model.BoqLine` (existing).
- Produces: `EXECUTION_LEDGER_EXTRACTION_PROMPT: str`, `ExecutionNapkinParseError(Exception)`, `ExecutionNapkinProvider` — constructor `(*, ocr_engine: OcrEngine, image_bytes: bytes, mime_type: str, evidence_id: int, tender_id: int, boq_lines: list[BoqLine], lock_ins: list[dict[str, Any]])`, method `generate(self, *, observed_at_fallback: str) -> list[ExecutionFact]` (Task 5 calls this; `observed_at_fallback` is used only when the OCR output's own `observed_at` is null — a photo taken today with no stated date should not silently become undated).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_execution_napkin_provider.py
from __future__ import annotations

import json
from decimal import Decimal

import pytest

from packages.decision.execution_napkin_provider import ExecutionNapkinParseError, ExecutionNapkinProvider
from packages.platform.ocr_engine import OcrEngine
from packages.tender.boq_line_model import BoqLine


class FakeOcrEngine(OcrEngine):
    def __init__(self, response_text: str) -> None:
        self._response_text = response_text

    def parse_document(self, image_bytes: bytes, *, mime_type: str) -> str:
        return self._response_text


def _line(source_line_id: int, description: str) -> BoqLine:
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
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )


def _provider(response_payload: dict, *, boq_lines=None, lock_ins=None) -> ExecutionNapkinProvider:
    return ExecutionNapkinProvider(
        ocr_engine=FakeOcrEngine(json.dumps(response_payload)),
        image_bytes=b"fake-jpeg",
        mime_type="image/jpeg",
        evidence_id=1,
        tender_id=99,
        boq_lines=boq_lines or [],
        lock_ins=lock_ins or [],
    )


def test_generate_produces_one_fact_per_observation():
    payload = {
        "observations": [
            {
                "line_description": "Rebar 12mm",
                "actual_qty": 15,
                "deviation_reason": "used more rebar than planned",
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload, boq_lines=[_line(501, "Rebar 12mm, grade B500B")])
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")

    assert len(facts) == 1
    assert facts[0].tender_id == 99
    assert facts[0].boqline_source_line_id == 501
    assert facts[0].planned_qty == Decimal("10")  # from the matched BOQ line, never the photo
    assert facts[0].actual_qty == Decimal("15")
    assert facts[0].culprit_type == "internal"
    assert facts[0].evidence_source == "napkin-ocr:1"


def test_generate_resolves_vendor_culprit_to_a_vendor_id():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "crane did not arrive, half-day idle",
                "deviation_category": "downtime",
                "culprit_type": "vendor",
                "culprit_vendor_name": "Acme Crane Co",
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload, lock_ins=[{"boqline_source_line_id": 1, "vendor_id": 42, "vendor_name": "Acme Crane Co"}])
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")

    assert facts[0].culprit_vendor_id == 42
    assert facts[0].culprit_vendor_name == "Acme Crane Co"
    assert facts[0].boqline_source_line_id is None
    assert facts[0].planned_qty is None


def test_generate_falls_back_to_the_supplied_date_when_observed_at_is_null():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "site was rained out",
                "deviation_category": "downtime",
                "culprit_type": "external",
                "culprit_vendor_name": None,
                "observed_at": None,
            }
        ]
    }
    provider = _provider(payload)
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")
    assert facts[0].observed_at == "2026-08-09T00:00:00+00:00"


def test_generate_handles_multiple_observations_in_one_capture():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "rework on formwork",
                "deviation_category": "rework",
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            },
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "site handover delayed by client",
                "deviation_category": "preliminaries",
                "culprit_type": "customer",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            },
        ]
    }
    provider = _provider(payload)
    facts = provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")
    assert len(facts) == 2
    assert {f.culprit_type for f in facts} == {"internal", "customer"}


def test_generate_raises_on_invalid_json():
    provider = ExecutionNapkinProvider(
        ocr_engine=FakeOcrEngine("not json"),
        image_bytes=b"x",
        mime_type="image/jpeg",
        evidence_id=1,
        tender_id=99,
        boq_lines=[],
        lock_ins=[],
    )
    with pytest.raises(ExecutionNapkinParseError, match="not valid JSON"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_when_observations_key_is_missing():
    provider = _provider({"not_observations": []})
    with pytest.raises(ExecutionNapkinParseError, match="observations"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_when_deviation_reason_is_missing():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": None,
                "deviation_category": None,
                "culprit_type": "internal",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="deviation_reason"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_on_unknown_culprit_type():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "something happened",
                "deviation_category": None,
                "culprit_type": "weather",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="culprit_type"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")


def test_generate_raises_when_vendor_culprit_has_no_name():
    payload = {
        "observations": [
            {
                "line_description": None,
                "actual_qty": None,
                "deviation_reason": "late delivery",
                "deviation_category": None,
                "culprit_type": "vendor",
                "culprit_vendor_name": None,
                "observed_at": "2026-08-10T00:00:00+00:00",
            }
        ]
    }
    provider = _provider(payload)
    with pytest.raises(ExecutionNapkinParseError, match="culprit_vendor_name"):
        provider.generate(observed_at_fallback="2026-08-09T00:00:00+00:00")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/unit/test_execution_napkin_provider.py -q` — expected FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

Create `packages/decision/execution_napkin_provider.py`:

```python
"""Real napkin-ingestion provider for the Execution Ledger (Phase 4, task
4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3, INV-18, P318) -- the
"photo of a completion act / voice note from site" half of napkin
ingestion, turning an OCR engine's extracted text into ExecutionFact
drafts. Same NapkinOcrProvider shape as packages/vendor/napkin_provider.py
but decision-domain: "planned" always comes from this codebase's own
already-stored BOQ line (execution_fact_resolution.py), never from the
photo/voice note -- a field-worker's guess at what was planned is not
authoritative.

EXECUTION_LEDGER_EXTRACTION_PROMPT and the JSON shape this parser expects
are THIS TASK'S OWN INVENTION, same honest limitation as
napkin_provider.py's NAPKIN_EXTRACTION_PROMPT: no source document supplies
a construction-site-deviation extraction schema, and no real captured
photo/voice note has been run through a real model in this session."""

from __future__ import annotations

import json
from decimal import Decimal
from typing import Any

from packages.platform.ocr_engine import OcrEngine
from packages.tender.boq_line_model import BoqLine

from .execution_fact_model import CULPRIT_TYPES, DEVIATION_CATEGORIES, ExecutionFact
from .execution_fact_resolution import resolve_boqline_reference, resolve_vendor_reference

EXECUTION_LEDGER_EXTRACTION_PROMPT = (
    "Extract every distinct execution deviation or observation from this "
    "document/note as JSON, exactly matching this shape, with no other "
    'text before or after the JSON: {"observations": [{"line_description": '
    'string | null, "actual_qty": number | null, "deviation_reason": '
    'string, "deviation_category": one of "preliminaries", "downtime", '
    '"rework", "last_mile", or null, "culprit_type": one of "vendor", '
    '"customer", "internal", "external", "culprit_vendor_name": string | '
    'null, "observed_at": ISO 8601 date string or null}]}. If a field is '
    "not stated in the image/note, use null -- never invent a value."
)


class ExecutionNapkinParseError(Exception):
    """The OCR engine's output isn't valid JSON, is missing the
    observations list, or an observation is missing a required field or
    names an unknown culprit_type/deviation_category -- always this one
    typed error, never a silently dropped observation."""


class ExecutionNapkinProvider:
    def __init__(
        self,
        *,
        ocr_engine: OcrEngine,
        image_bytes: bytes,
        mime_type: str,
        evidence_id: int,
        tender_id: int,
        boq_lines: list[BoqLine],
        lock_ins: list[dict[str, Any]],
    ) -> None:
        self._ocr_engine = ocr_engine
        self._image_bytes = image_bytes
        self._mime_type = mime_type
        self._evidence_id = evidence_id
        self._tender_id = tender_id
        self._boq_lines = boq_lines
        self._lock_ins = lock_ins

    def generate(self, *, observed_at_fallback: str) -> list[ExecutionFact]:
        raw_text = self._ocr_engine.parse_document(self._image_bytes, mime_type=self._mime_type)
        try:
            payload = json.loads(raw_text)
        except json.JSONDecodeError as exc:
            raise ExecutionNapkinParseError(f"OCR output is not valid JSON: {exc}") from exc

        if not isinstance(payload, dict) or not isinstance(payload.get("observations"), list):
            raise ExecutionNapkinParseError(f"OCR output is missing an 'observations' list: {raw_text!r}")

        evidence_source = f"napkin-ocr:{self._evidence_id}"
        facts: list[ExecutionFact] = []
        for obs in payload["observations"]:
            if not isinstance(obs, dict):
                raise ExecutionNapkinParseError(f"observation is not an object: {obs!r}")

            deviation_reason = obs.get("deviation_reason")
            if not deviation_reason:
                raise ExecutionNapkinParseError(f"observation is missing a non-empty 'deviation_reason': {obs!r}")

            culprit_type = obs.get("culprit_type")
            if culprit_type not in CULPRIT_TYPES:
                raise ExecutionNapkinParseError(f"observation has unknown culprit_type: {culprit_type!r}")

            deviation_category = obs.get("deviation_category")
            if deviation_category is not None and deviation_category not in DEVIATION_CATEGORIES:
                raise ExecutionNapkinParseError(f"observation has unknown deviation_category: {deviation_category!r}")

            culprit_vendor_name = obs.get("culprit_vendor_name")
            if culprit_type == "vendor" and not culprit_vendor_name:
                raise ExecutionNapkinParseError("observation has culprit_type 'vendor' but no culprit_vendor_name")
            if culprit_type != "vendor":
                culprit_vendor_name = None

            matched_line = resolve_boqline_reference(self._boq_lines, obs.get("line_description"))
            culprit_vendor_id = (
                resolve_vendor_reference(self._lock_ins, culprit_vendor_name) if culprit_type == "vendor" else None
            )

            actual_qty_raw = obs.get("actual_qty")
            observed_at = obs.get("observed_at") or observed_at_fallback

            facts.append(
                ExecutionFact(
                    tender_id=self._tender_id,
                    boqline_source_line_id=matched_line.source_line_id if matched_line else None,
                    planned_qty=matched_line.qty if matched_line else None,
                    actual_qty=None if actual_qty_raw is None else Decimal(str(actual_qty_raw)),
                    deviation_reason=str(deviation_reason),
                    deviation_category=deviation_category,
                    culprit_type=culprit_type,
                    culprit_vendor_name=culprit_vendor_name,
                    culprit_vendor_id=culprit_vendor_id,
                    evidence_source=evidence_source,
                    observed_at=observed_at,
                )
            )

        return facts
```

Add `from decimal import Decimal` to this file's top-level imports (alongside `import json` and the `typing`/`packages...` imports already listed above).

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/unit/test_execution_napkin_provider.py -q` — expected PASS.
Run: `python -m ruff check packages/decision/execution_napkin_provider.py` — must be clean.

- [ ] **Step 5: Commit**

```bash
git add packages/decision/execution_napkin_provider.py tests/unit/test_execution_napkin_provider.py
git commit -m "feat(decision): napkin OCR extraction into ExecutionFact drafts (task 4.C)"
```

---

### Task 5: Vendor reputation feed — cross-service contract + internal endpoint

**Files:**
- Modify: `packages/contracts/vendor_api.py` (add a write call)
- Modify: `apps/api_vendor/routers/internal.py` (add `POST /internal/reputation-facts`)
- Create: `packages/decision/reputation_feed.py`
- Test: `tests/unit/test_reputation_feed.py`, `tests/contract/test_tender_vendor_contract.py` (extend), `tests/integration/test_internal_reputation_facts_route.py`

**Interfaces:**
- Consumes: `packages.vendor.reputation_model.ReputationFact`/`REPUTATION_EVENT_TYPES` (existing), `packages.vendor.reputation_store.store_reputation_fact` (existing).
- Produces: `packages.decision.reputation_feed.map_to_reputation_event_type(deviation_category: str | None, culprit_type: str) -> str | None` — returns an existing `packages.vendor.reputation_model` event type only for an exact, unambiguous mapping (`culprit_type == "vendor"` and `deviation_category in ("downtime", "last_mile")` → `"missed_deadline"`; `deviation_category == "rework"` → `"quality_complaint"`; anything else → `None`, never guessed). `packages.contracts.vendor_api.report_reputation_fact(base_url, *, vendor_id: int, event_type: str, project_ref: str, source_ref: str, observed_at: str, ttl_days: int, correlation_id: str | None = None, client: httpx.AsyncClient | None = None) -> None`. `POST /internal/reputation-facts` on the Vendor service, request body `{vendor_id, event_type, project_ref, source_ref, observed_at, ttl_days}`, `data_realm`/`watermark` hardcoded `"vendor-sandbox"`/`"SYNTHETIC"` server-side (same ADR-0004 pre-legal-gate realm every other write in this codebase uses today), 201 on success.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_reputation_feed.py
from __future__ import annotations

from packages.decision.reputation_feed import map_to_reputation_event_type


def test_vendor_downtime_maps_to_missed_deadline():
    assert map_to_reputation_event_type("downtime", "vendor") == "missed_deadline"


def test_vendor_last_mile_maps_to_missed_deadline():
    assert map_to_reputation_event_type("last_mile", "vendor") == "missed_deadline"


def test_vendor_rework_maps_to_quality_complaint():
    assert map_to_reputation_event_type("rework", "vendor") == "quality_complaint"


def test_vendor_preliminaries_has_no_clean_mapping():
    assert map_to_reputation_event_type("preliminaries", "vendor") is None


def test_vendor_none_category_has_no_mapping():
    assert map_to_reputation_event_type(None, "vendor") is None


def test_non_vendor_culprit_never_maps_regardless_of_category():
    assert map_to_reputation_event_type("downtime", "customer") is None
    assert map_to_reputation_event_type("rework", "internal") is None
    assert map_to_reputation_event_type("downtime", "external") is None
```

```python
# tests/integration/test_internal_reputation_facts_route.py
from __future__ import annotations

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_vendor.main import create_app
from packages.platform.settings import Settings
from packages.vendor.vendor_model import Vendor
from packages.vendor.vendor_store import store_vendor


@pytest_asyncio.fixture
async def app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    application = create_app(settings)
    application.state.engine = engine
    return application


@pytest_asyncio.fixture
async def client(app):
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as c:
        yield c


async def test_post_reputation_fact_persists_it(client, engine):
    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(
            conn, Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Acme Crane Co", provider_type="test", seed=1)
        )

    response = await client.post(
        "/internal/reputation-facts",
        json={
            "vendor_id": vendor_id,
            "event_type": "missed_deadline",
            "project_ref": "99",
            "source_ref": "napkin-ocr:1",
            "observed_at": "2026-08-10T00:00:00+00:00",
            "ttl_days": 365,
        },
    )
    assert response.status_code == 201

    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT event_type, project_ref FROM vendor_reputation_facts WHERE vendor_id = :v"),
                    {"v": vendor_id},
                )
            )
            .mappings()
            .one()
        )
    assert row["event_type"] == "missed_deadline"
    assert row["project_ref"] == "99"


async def test_post_reputation_fact_rejects_unknown_event_type(client, engine):
    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(
            conn, Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Beta Co", provider_type="test", seed=2)
        )

    response = await client.post(
        "/internal/reputation-facts",
        json={
            "vendor_id": vendor_id,
            "event_type": "not_a_real_event_type",
            "project_ref": "99",
            "source_ref": "napkin-ocr:1",
            "observed_at": "2026-08-10T00:00:00+00:00",
            "ttl_days": 365,
        },
    )
    assert response.status_code == 422
```

Add to `tests/contract/test_tender_vendor_contract.py` (extends the existing shared provider-contract test file with a client-side contract check for the new write call -- follows that file's existing pattern: no `vendor_app` fixture exists in this file, each test builds one inline from the `engine`/`_database_url` fixtures already used by every other test here, with `expected_schema_version=16`, matching Task 2's bump):

```python
async def test_report_reputation_fact_round_trips_over_real_http(engine, _database_url):
    from sqlalchemy import text

    from packages.contracts.vendor_api import report_reputation_fact
    from packages.vendor.vendor_model import Vendor
    from packages.vendor.vendor_store import store_vendor

    settings = Settings(database_url=_database_url, expected_schema_version=16)
    vendor_app = create_vendor_app(settings)
    vendor_app.state.engine = engine

    async with engine.begin() as conn:
        vendor_id, _api_key = await store_vendor(
            conn, Vendor(data_realm="vendor-sandbox", watermark="SYNTHETIC", name="Gamma Co", provider_type="test", seed=3)
        )

    transport = httpx.ASGITransport(app=vendor_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=transport, base_url="http://vendor-test") as client:
        await report_reputation_fact(
            "http://vendor-test",
            vendor_id=vendor_id,
            event_type="quality_complaint",
            project_ref="42",
            source_ref="napkin-ocr:7",
            observed_at="2026-08-10T00:00:00+00:00",
            ttl_days=180,
            client=client,
        )

    async with engine.begin() as conn:
        row = (
            (await conn.execute(text("SELECT event_type FROM vendor_reputation_facts WHERE vendor_id = :v"), {"v": vendor_id}))
            .mappings()
            .one()
        )
    assert row["event_type"] == "quality_complaint"
```

Also bump this file's three EXISTING `expected_schema_version=15` calls to `16` as part of this task's step (same schema-version-bump discipline Task 2 already applies to `tests/`) — this file is only touched by tasks that bump the schema version, and 4.C is the first to do so since it was last edited.

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/unit/test_reputation_feed.py -q` — expected FAIL (`ModuleNotFoundError`).
Run: `python -m pytest tests/integration/test_internal_reputation_facts_route.py -q` — expected FAIL (404, route doesn't exist).

- [ ] **Step 3: Implement**

Create `packages/decision/reputation_feed.py`:

```python
"""Maps an Execution Ledger deviation to an EXISTING vendor ReputationFact
event_type (Phase 4, task 4.C, feeding SCG's task 3.B reputation layer) --
never a new event_type, never a weighted score (D-VND-REP is still open
and untouched by this module). Only culprit_type == "vendor" observations
ever produce a mapping; anything else returns None, and an unmapped
deviation_category also returns None rather than guessing the closest
existing type."""

from __future__ import annotations

_CATEGORY_TO_EVENT_TYPE = {
    "downtime": "missed_deadline",
    "last_mile": "missed_deadline",
    "rework": "quality_complaint",
}


def map_to_reputation_event_type(deviation_category: str | None, culprit_type: str) -> str | None:
    if culprit_type != "vendor" or deviation_category is None:
        return None
    return _CATEGORY_TO_EVENT_TYPE.get(deviation_category)
```

In `packages/contracts/vendor_api.py`, add (after `list_vendor_offers`):

```python
class ReportReputationFactRequest(BaseModel):
    vendor_id: int
    event_type: str
    project_ref: str
    source_ref: str
    observed_at: str
    ttl_days: int


async def report_reputation_fact(
    base_url: str,
    *,
    vendor_id: int,
    event_type: str,
    project_ref: str,
    source_ref: str,
    observed_at: str,
    ttl_days: int,
    correlation_id: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> None:
    resolved_correlation_id = correlation_id or get_correlation_id_or_none()
    headers = {CORRELATION_ID_HEADER: resolved_correlation_id} if resolved_correlation_id else {}
    body = ReportReputationFactRequest(
        vendor_id=vendor_id,
        event_type=event_type,
        project_ref=project_ref,
        source_ref=source_ref,
        observed_at=observed_at,
        ttl_days=ttl_days,
    )

    owns_client = client is None
    http_client = client or httpx.AsyncClient()
    try:
        response = await http_client.post(
            f"{base_url}/internal/reputation-facts",
            json=body.model_dump(),
            headers=headers,
            timeout=10.0,
        )
    except httpx.HTTPError as exc:
        raise VendorApiError(f"vendor service unreachable: {exc}") from exc
    finally:
        if owns_client:
            await http_client.aclose()

    if response.status_code not in (200, 201):
        raise VendorApiError(f"vendor service returned status {response.status_code}: {response.text}")
```

In `apps/api_vendor/routers/internal.py`, add (near the bottom, after `list_internal_offers`):

```python
from packages.vendor.reputation_model import REPUTATION_EVENT_TYPES, ReputationFact
from packages.vendor.reputation_store import store_reputation_fact


class ReportReputationFactRequest(BaseModel):
    vendor_id: int
    event_type: str
    project_ref: str
    source_ref: str
    observed_at: str
    ttl_days: int


@router.post("/internal/reputation-facts", status_code=201)
async def report_reputation_fact(
    body: ReportReputationFactRequest,
    conn: AsyncConnection = Depends(get_connection),
) -> dict[str, int]:
    if body.event_type not in REPUTATION_EVENT_TYPES:
        raise HTTPException(status_code=422, detail=f"unknown event_type: {body.event_type!r}")

    fact = ReputationFact(
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        vendor_name="",  # unused by store_reputation_fact -- vendor_id is the real key
        event_type=body.event_type,
        project_ref=body.project_ref,
        source_ref=body.source_ref,
        observed_at=body.observed_at,
        ttl_days=body.ttl_days,
    )
    fact_id = await store_reputation_fact(conn, body.vendor_id, fact)
    return {"id": fact_id}
```

(add `from fastapi import HTTPException` to this file's existing `from fastapi import APIRouter, Depends` import line.)

Confirmed by reading `packages/vendor/reputation_store.py::store_reputation_fact`'s SQL: it inserts `vendor_id` as its own bound parameter and never reads `fact.vendor_name` at all (the `INSERT` column list is `vendor_id, data_realm, watermark, event_type, project_ref, source_ref, observed_at, ttl_days` — no `vendor_name` column exists on `vendor_reputation_facts`). Passing `vendor_name=""` on the `ReputationFact` constructed above is therefore safe, not a guess — the field is a construction-time-only artifact of the dataclass shape, never persisted or read back.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/unit/test_reputation_feed.py tests/integration/test_internal_reputation_facts_route.py tests/contract/test_tender_vendor_contract.py -q` — expected PASS.
Run: `python -m ruff check packages/decision/reputation_feed.py packages/contracts/vendor_api.py apps/api_vendor/routers/internal.py`

- [ ] **Step 5: Commit**

```bash
git add packages/decision/reputation_feed.py packages/contracts/vendor_api.py apps/api_vendor/routers/internal.py tests/unit/test_reputation_feed.py tests/integration/test_internal_reputation_facts_route.py tests/contract/test_tender_vendor_contract.py
git commit -m "feat(vendor,contracts,decision): vendor reputation feed from Execution Ledger deviations (task 4.C)"
```

---

### Task 6: API route — submit napkin capture, list execution facts

**Files:**
- Create: `apps/api_tender/routers/execution_ledger.py`
- Modify: `apps/api_tender/main.py` (register the new router)
- Test: `tests/integration/test_execution_ledger_api.py`

**Interfaces:**
- Consumes: everything from Tasks 2-5, plus existing `packages.tender.boq_lines_store.list_boq_lines_by_event`, `packages.tender.normalized.get_event_id_for_tender`, `packages.decision.decision_store.list_lock_in_requirements_by_tender`, `packages.platform.rbac.dependency.require_permission`, `packages.platform.audit.write_audit_log`, `packages.platform.exception_queue.enqueue_exception`, `packages.contracts.vendor_api.report_reputation_fact`/`VendorApiError`.
- Produces: `POST /tenders/{tender_id}/execution-facts/napkin` (permission `decision.execution_facts.create`), `GET /tenders/{tender_id}/execution-facts` (permission `decision.execution_facts.read`).

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_execution_ledger_api.py
from __future__ import annotations

import base64
import json
from decimal import Decimal

import httpx
import pytest_asyncio
from sqlalchemy import text

from apps.api_tender.main import create_app as create_tender_app
from apps.api_vendor.main import create_app as create_vendor_app
from packages.decision.decision_model import Decision
from packages.decision.decision_store import store_decision, store_lock_in_requirement
from packages.platform.settings import Settings
from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

EXECUTION_LEDGER_PERMISSIONS = ("decision.execution_facts.create", "decision.execution_facts.read")


@pytest_asyncio.fixture
async def tender_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
    app = create_tender_app(settings)
    app.state.engine = engine
    return app


@pytest_asyncio.fixture
async def vendor_app(engine, _database_url):
    settings = Settings(database_url=_database_url, expected_schema_version=16)
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
        expected_schema_version=16,
        vendor_service_base_url="http://vendor-test",
    )
    tender_transport = httpx.ASGITransport(app=tender_app, raise_app_exceptions=False)
    async with httpx.AsyncClient(transport=tender_transport, base_url="http://tender-test") as c:
        yield c
    await vendor_client.aclose()


@pytest_asyncio.fixture
async def pm_user(engine):
    async with engine.begin() as conn:
        role_id = (await conn.execute(text("INSERT INTO roles (name) VALUES ('pm-el') RETURNING id"))).scalar()
        for perm in EXECUTION_LEDGER_PERMISSIONS:
            perm_id = (
                await conn.execute(text("INSERT INTO permissions (name) VALUES (:name) RETURNING id"), {"name": perm})
            ).scalar()
            await conn.execute(
                text("INSERT INTO role_permissions (role_id, permission_id) VALUES (:r, :p)"),
                {"r": role_id, "p": perm_id},
            )
        await conn.execute(
            text("INSERT INTO users (username, display_name, role_id) VALUES ('pm-el-1', 'PM EL', :r)"), {"r": role_id}
        )
    return "pm-el-1"


@pytest_asyncio.fixture
async def tender_with_boq_and_lock_in(engine):
    line = BoqLine(
        source_line_id=501,
        page_number=1,
        section=None,
        category_code=None,
        description="Rebar 12mm, grade B500B",
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
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-api-1",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-api-1",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-api-1")
        version = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"id": 800001},
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=800001,
            tender_version_id=version.id,
            raw_snapshot_id=snapshot_id,
            lines=[line],
        )
        # lock_in_requirements.decision_id is a real FK to decisions -- a
        # decision row must exist first, not an arbitrary literal id.
        decision_id = await store_decision(
            conn,
            Decision(
                tender_id=tender_id,
                decision_type="bid",
                conditions=(),
                deadline=None,
                justification="test",
                actor="pm-el-1",
                decided_at="2026-08-10T00:00:00+00:00",
                go_no_go_inputs_id=None,
                bid_readiness_candidate_id=None,
            ),
        )
        await store_lock_in_requirement(
            conn,
            tender_id=tender_id,
            decision_id=decision_id,
            boqline_source_line_id=501,
            vendor_id=42,
            vendor_name="Acme Crane Co",
        )
    return tender_id


async def test_napkin_submission_requires_auth(client, tender_with_boq_and_lock_in):
    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"x").decode()},
    )
    assert response.status_code == 401


async def test_voice_capture_stores_evidence_but_is_not_parsed(client, pm_user, tender_with_boq_and_lock_in):
    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "voice", "mime_type": "audio/ogg", "image_base64": base64.b64encode(b"voice-bytes").decode()},
        headers={"X-User": pm_user},
    )
    assert response.status_code == 201
    body = response.json()
    assert body["parsed"] is False
    assert body["facts"] == []
    assert body["evidence_id"] is not None


async def test_photo_submission_returns_503_when_ocr_not_configured(client, pm_user, tender_with_boq_and_lock_in, monkeypatch):
    # Hard ban #3 (no silent fallback): an unconfigured OCR backend must be
    # a real, loud error, never a silent no-op or a guessed model name.
    monkeypatch.delenv("OCR_MODEL_NAME", raising=False)
    response = await client.post(
        f"/tenders/{tender_with_boq_and_lock_in}/execution-facts/napkin",
        json={"capture_kind": "photo", "mime_type": "image/jpeg", "image_base64": base64.b64encode(b"jpeg-bytes").decode()},
        headers={"X-User": pm_user},
    )
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "ocr_not_configured"


async def test_list_execution_facts_returns_stored_facts(client, pm_user, tender_with_boq_and_lock_in, engine):
    from packages.decision.execution_fact_model import ExecutionFact
    from packages.decision.execution_ledger_store import store_execution_fact

    async with engine.begin() as conn:
        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_with_boq_and_lock_in,
                boqline_source_line_id=501,
                planned_qty=Decimal("10"),
                actual_qty=Decimal("15"),
                deviation_reason="used more rebar than planned",
                deviation_category=None,
                culprit_type="internal",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:1",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    response = await client.get(f"/tenders/{tender_with_boq_and_lock_in}/execution-facts", headers={"X-User": pm_user})
    assert response.status_code == 200
    body = response.json()
    assert len(body["items"]) == 1
    assert body["items"][0]["boqline_source_line_id"] == 501
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integration/test_execution_ledger_api.py -q` — expected FAIL (404, router not registered).

- [ ] **Step 3: Implement**

Create `apps/api_tender/routers/execution_ledger.py`:

```python
"""Execution Ledger routes (Phase 4, task 4.C, TENDER_INTELLIGENCE_SPEC.md
Section7.3, P318). Evidence is always saved first, before any parse attempt
(INV-18: capture must never depend on whether the system currently
understands it). A 'voice' capture is stored but not parsed -- ASR is
still an open tech-choice gap (docs/decisions/OPEN-QUESTIONS.md), same as
packages/vendor's napkin ingestion. OCR config comes from
packages/platform/ocr_settings.py; an unconfigured OCR backend is a real,
loud 503, never a silent no-op (AGENTS.md hard ban #3)."""

from __future__ import annotations

import base64
from datetime import UTC, datetime
from decimal import Decimal
from typing import Any

import httpx
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.contracts.vendor_api import VendorApiError, report_reputation_fact
from packages.decision.decision_store import list_lock_in_requirements_by_tender
from packages.decision.execution_fact_model import ExecutionFact
from packages.decision.execution_ledger_store import list_execution_facts_by_tender, store_execution_fact
from packages.decision.execution_napkin_evidence import save_execution_napkin_evidence
from packages.decision.execution_napkin_provider import ExecutionNapkinParseError, ExecutionNapkinProvider
from packages.decision.reputation_feed import map_to_reputation_event_type
from packages.platform.audit import write_audit_log
from packages.platform.errors import ApiError
from packages.platform.exception_queue import enqueue_exception
from packages.platform.ocr_engine import OcrEngineError
from packages.platform.ocr_settings import get_ocr_settings
from packages.platform.ollama_ocr_engine import OllamaOcrEngine
from packages.platform.rbac.dependency import require_permission
from packages.platform.rbac.models import Identity
from packages.tender.boq_lines_store import list_boq_lines_by_event
from packages.tender.normalized import get_event_id_for_tender

from ..deps import get_connection, get_current_identity, get_vendor_http_client

router = APIRouter(prefix="/tenders/{tender_id}", tags=["execution-ledger"])


class NapkinSubmissionRequest(BaseModel):
    capture_kind: str
    mime_type: str
    image_base64: str
    # No default: INV-17 explicitly leaves exact TTL numbers for the
    # qualification/reputation fact class as TBD-TIS-01 ("не решены"),
    # the same regime as PRD's TBD-01 -- this codebase's own
    # synthetic_reputation.py only ever samples an arbitrary TTL for
    # SYNTHETIC demo data, never for a fact stemming from a real
    # observation. A vendor-culprit fact with a mappable event_type is
    # therefore only reported to the Vendor service when the caller
    # supplies this explicitly; otherwise it is queued for a human to
    # decide (see below), never silently defaulted.
    reputation_ttl_days: int | None = None


class ExecutionFactResponse(BaseModel):
    boqline_source_line_id: int | None
    planned_qty: str | None
    actual_qty: str | None
    deviation_reason: str
    deviation_category: str | None
    culprit_type: str
    culprit_vendor_name: str | None
    culprit_vendor_id: int | None
    evidence_source: str
    observed_at: str


class NapkinSubmissionResponse(BaseModel):
    evidence_id: int
    parsed: bool
    facts: list[ExecutionFactResponse]


class ExecutionFactListResponse(BaseModel):
    items: list[dict[str, Any]]


@router.post("/execution-facts/napkin", response_model=NapkinSubmissionResponse, status_code=201)
async def submit_napkin_capture(
    tender_id: int,
    body: NapkinSubmissionRequest,
    request: Request,
    conn: AsyncConnection = Depends(get_connection),
    vendor_http_client: httpx.AsyncClient | None = Depends(get_vendor_http_client),
    identity: Identity = Depends(require_permission("decision.execution_facts.create", get_current_identity)),
) -> NapkinSubmissionResponse:
    raw_bytes = base64.b64decode(body.image_base64)
    correlation_id = f"execution-ledger-napkin-{tender_id}"
    evidence_id = await save_execution_napkin_evidence(
        conn,
        tender_id=tender_id,
        capture_kind=body.capture_kind,
        raw_bytes=raw_bytes,
        mime_type=body.mime_type,
        correlation_id=correlation_id,
    )

    if body.capture_kind == "voice":
        return NapkinSubmissionResponse(evidence_id=evidence_id, parsed=False, facts=[])

    settings = get_ocr_settings()
    if not settings.ocr_model_name:
        raise ApiError(status_code=503, code="ocr_not_configured", message="OCR_MODEL_NAME is not set")
    ocr_engine = OllamaOcrEngine(base_url=settings.ollama_base_url, model_name=settings.ocr_model_name)

    event_id = await get_event_id_for_tender(conn, tender_id=tender_id)
    boq_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id) if event_id is not None else []
    lock_ins = await list_lock_in_requirements_by_tender(conn, tender_id=tender_id)

    provider = ExecutionNapkinProvider(
        ocr_engine=ocr_engine,
        image_bytes=raw_bytes,
        mime_type=body.mime_type,
        evidence_id=evidence_id,
        tender_id=tender_id,
        boq_lines=boq_lines,
        lock_ins=lock_ins,
    )
    observed_at_fallback = datetime.now(UTC).isoformat()
    try:
        drafts = provider.generate(observed_at_fallback=observed_at_fallback)
    except (ExecutionNapkinParseError, OcrEngineError) as exc:
        await enqueue_exception(
            conn,
            source="execution-ledger",
            exception_type="napkin_unrecognized",
            category="needs_human",
            reason=str(exc),
            correlation_id=correlation_id,
            raw_ref=evidence_id,
            contract_name=None,
        )
        raise ApiError(status_code=422, code="napkin_unrecognized", message=str(exc)) from exc

    stored: list[ExecutionFact] = []
    for fact in drafts:
        await store_execution_fact(conn, fact)
        stored.append(fact)
        event_type = map_to_reputation_event_type(fact.deviation_category, fact.culprit_type)
        if event_type is not None and fact.culprit_vendor_id is not None:
            if body.reputation_ttl_days is None:
                # TBD-TIS-01 (INV-17): no approved TTL number exists for a
                # real reputation/qualification-class fact -- surface the
                # gap rather than guess one, hard ban #3.
                await enqueue_exception(
                    conn,
                    source="execution-ledger",
                    exception_type="vendor_reputation_ttl_missing",
                    category="needs_human",
                    reason=(
                        f"vendor {fact.culprit_vendor_id} reputation fact ({event_type}) ready but "
                        "reputation_ttl_days was not supplied (TBD-TIS-01)"
                    ),
                    correlation_id=correlation_id,
                    raw_ref=evidence_id,
                    contract_name=None,
                )
            else:
                try:
                    await report_reputation_fact(
                        request.app.state.settings.vendor_service_base_url,
                        vendor_id=fact.culprit_vendor_id,
                        event_type=event_type,
                        project_ref=str(tender_id),
                        source_ref=fact.evidence_source,
                        observed_at=fact.observed_at,
                        ttl_days=body.reputation_ttl_days,
                        client=vendor_http_client,
                    )
                except VendorApiError:
                    await enqueue_exception(
                        conn,
                        source="execution-ledger",
                        exception_type="vendor_reputation_feed_failed",
                        category="needs_human",
                        reason=f"could not report reputation fact for vendor {fact.culprit_vendor_id}",
                        correlation_id=correlation_id,
                        raw_ref=evidence_id,
                        contract_name=None,
                    )

    await write_audit_log(
        conn,
        actor=identity.subject,
        action="execution_facts.create",
        object_type="execution_napkin_evidence",
        object_id=str(evidence_id),
        object_version=None,
        reason=None,
    )

    return NapkinSubmissionResponse(
        evidence_id=evidence_id,
        parsed=True,
        facts=[
            ExecutionFactResponse(
                boqline_source_line_id=f.boqline_source_line_id,
                planned_qty=str(f.planned_qty) if f.planned_qty is not None else None,
                actual_qty=str(f.actual_qty) if f.actual_qty is not None else None,
                deviation_reason=f.deviation_reason,
                deviation_category=f.deviation_category,
                culprit_type=f.culprit_type,
                culprit_vendor_name=f.culprit_vendor_name,
                culprit_vendor_id=f.culprit_vendor_id,
                evidence_source=f.evidence_source,
                observed_at=f.observed_at,
            )
            for f in stored
        ],
    )


@router.get("/execution-facts", response_model=ExecutionFactListResponse)
async def get_execution_facts(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.read", get_current_identity)),
) -> ExecutionFactListResponse:
    facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)
    return ExecutionFactListResponse(items=facts)
```

The Vendor service base URL and shared `httpx.AsyncClient` come from `request.app.state.settings.vendor_service_base_url` / `Depends(get_vendor_http_client)`, the same pattern `apps/api_tender/routers/decision.py::get_bid_readiness_candidate` already uses for its own cross-service call — already wired into the imports and route signature above.

`apps/api_tender/main.py` currently reads:
```python
from .routers import admin_users, decision, health
...
    app.include_router(health.router)
    app.include_router(admin_users.router)
    app.include_router(decision.router)
    return app
```
Change the import line to add the new module, and add one more `include_router` line matching the existing style exactly (whole-module import, `.router` attribute access):
```python
from .routers import admin_users, decision, execution_ledger, health
...
    app.include_router(health.router)
    app.include_router(admin_users.router)
    app.include_router(decision.router)
    app.include_router(execution_ledger.router)
    return app
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integration/test_execution_ledger_api.py -q` — expected PASS.
Run: `python -m ruff check apps/api_tender/routers/execution_ledger.py apps/api_tender/main.py`
Run: `python -m mypy packages apps` — fix any type errors surfaced by the new route.

- [ ] **Step 5: Commit**

```bash
git add apps/api_tender/routers/execution_ledger.py apps/api_tender/main.py tests/integration/test_execution_ledger_api.py
git commit -m "feat(api-tender): napkin capture submission and execution-facts read route (task 4.C)"
```

---

### Task 7: Project closure summary + buyer/customer execution history

**Files:**
- Create: `packages/decision/execution_ledger_summary.py`
- Modify: `packages/decision/execution_ledger_store.py` (add two functions)
- Modify: `apps/api_tender/routers/execution_ledger.py` (add two routes)
- Test: `tests/unit/test_execution_ledger_summary.py`, `tests/integration/test_execution_ledger_store.py` (extend), `tests/integration/test_execution_ledger_api.py` (extend)

**Interfaces:**
- Consumes: `packages.decision.execution_fact_model.DEVIATION_CATEGORIES` (existing), `list_execution_facts_by_tender` (existing).
- Produces:
  - `packages.decision.execution_ledger_summary.PlanFactDelta` (frozen dataclass: `boqline_source_line_id: int`, `planned_qty: Decimal`, `actual_qty: Decimal`, `delta: Decimal`), `summarize_plan_fact_deltas(facts: list[dict[str, Any]]) -> tuple[PlanFactDelta, ...]` — one row per `boqline_source_line_id` that has both a non-null `planned_qty` and `actual_qty` in at least one fact (a fact with either null is excluded, never coerced to zero — hard ban #3), sorted by `boqline_source_line_id`. `summarize_deviation_category_counts(facts: list[dict[str, Any]]) -> dict[str, int]` — count of facts per non-null `deviation_category`, only the four spec tokens as keys (a fact with `None` category contributes to no key).
  - `packages.decision.execution_ledger_store.store_overhead_buffer_contribution(conn, *, tender_id: int, deviation_category: str, fact_count: int, contributed_at: str) -> int`, `list_execution_facts_by_organization_voen(conn, *, organization_voen: str) -> list[dict[str, Any]]` (joins the latest `tender_versions.normalized_fields->>'organization_voen'` per tender against `execution_facts.culprit_type = 'customer'`).
  - `GET /tenders/{tender_id}/execution-summary` (permission `decision.execution_facts.read`) returns the plan/fact deltas and category counts without writing anything.
  - `POST /tenders/{tender_id}/close-project` (permission `decision.execution_facts.close_project`) persists one `overhead_buffer_contributions` row per non-zero category count and returns the same summary.
  - `GET /organizations/{organization_voen}/execution-history` (permission `decision.execution_facts.read`) returns customer-culprit facts across every tender sharing that VOEN, for a human to consult while filling in `GoNoGoInputs.customer_reputation_notes` on a future tender — read-only, never auto-injected into any decision.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_execution_ledger_summary.py
from __future__ import annotations

from decimal import Decimal

from packages.decision.execution_ledger_summary import summarize_deviation_category_counts, summarize_plan_fact_deltas


def _fact(**overrides) -> dict:
    defaults = dict(
        boqline_source_line_id=501,
        planned_qty=Decimal("10"),
        actual_qty=Decimal("15"),
        deviation_category="downtime",
    )
    defaults.update(overrides)
    return defaults


def test_summarize_plan_fact_deltas_computes_the_delta():
    facts = [_fact()]
    result = summarize_plan_fact_deltas(facts)
    assert result == (
        type(result[0])(boqline_source_line_id=501, planned_qty=Decimal("10"), actual_qty=Decimal("15"), delta=Decimal("5")),
    )


def test_summarize_plan_fact_deltas_excludes_facts_missing_either_side():
    facts = [_fact(planned_qty=None), _fact(boqline_source_line_id=502, actual_qty=None)]
    assert summarize_plan_fact_deltas(facts) == ()


def test_summarize_plan_fact_deltas_excludes_facts_with_no_boqline_reference():
    facts = [_fact(boqline_source_line_id=None)]
    assert summarize_plan_fact_deltas(facts) == ()


def test_summarize_plan_fact_deltas_is_sorted_by_line_id():
    facts = [_fact(boqline_source_line_id=502), _fact(boqline_source_line_id=501)]
    result = summarize_plan_fact_deltas(facts)
    assert [d.boqline_source_line_id for d in result] == [501, 502]


def test_summarize_deviation_category_counts_counts_each_category():
    facts = [_fact(deviation_category="downtime"), _fact(deviation_category="downtime"), _fact(deviation_category="rework")]
    assert summarize_deviation_category_counts(facts) == {"downtime": 2, "rework": 1}


def test_summarize_deviation_category_counts_ignores_none_category():
    facts = [_fact(deviation_category=None)]
    assert summarize_deviation_category_counts(facts) == {}
```

```python
# tests/integration/test_execution_ledger_store.py -- add these tests (reuses
# this file's existing _fact helper defined in Task 2). Add `from sqlalchemy
# import text` to this file's imports -- Task 2's own tests never needed it
# directly (they only call store_execution_fact/list_execution_facts_by_tender),
# but test_store_overhead_buffer_contribution below asserts via a raw SELECT.
from sqlalchemy import text

from packages.decision.execution_ledger_store import (
    list_execution_facts_by_organization_voen,
    store_overhead_buffer_contribution,
)
from packages.tender.normalized import create_normalized_version
from packages.tender.raw_snapshot import save_raw_snapshot


async def test_store_overhead_buffer_contribution(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-store-4")
        contribution_id = await store_overhead_buffer_contribution(
            conn, tender_id=tender_id, deviation_category="downtime", fact_count=3, contributed_at="2026-08-10T00:00:00+00:00"
        )
        row = (
            (
                await conn.execute(
                    text("SELECT tender_id, deviation_category, fact_count FROM overhead_buffer_contributions WHERE id = :id"),
                    {"id": contribution_id},
                )
            )
            .mappings()
            .one()
        )
    assert row["tender_id"] == tender_id
    assert row["deviation_category"] == "downtime"
    assert row["fact_count"] == 3


async def test_list_execution_facts_by_organization_voen_matches_across_tenders(engine):
    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-org-1",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-org-1",
        )
        tender_a = await get_or_create_tender(conn, source="etender", identity_key="test-4c-org-1")
        await create_normalized_version(
            conn,
            tender_id=tender_a,
            raw_snapshot_id=snapshot_id,
            parser_version="v1",
            normalized_fields={"organization_voen": "1000000001"},
        )
        await store_execution_fact(
            conn,
            _fact(
                tender_a,
                culprit_type="customer",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                deviation_category="preliminaries",
            ),
        )

        snapshot_id_2 = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="test-4c-org-2",
            raw_body=b"{}",
            contract_version="etender.event_details",
            correlation_id="test-4c-org-2",
        )
        tender_b = await get_or_create_tender(conn, source="etender", identity_key="test-4c-org-2")
        await create_normalized_version(
            conn,
            tender_id=tender_b,
            raw_snapshot_id=snapshot_id_2,
            parser_version="v1",
            normalized_fields={"organization_voen": "9999999999"},
        )
        await store_execution_fact(
            conn,
            _fact(
                tender_b,
                culprit_type="customer",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                deviation_category="preliminaries",
            ),
        )

        result = await list_execution_facts_by_organization_voen(conn, organization_voen="1000000001")

    assert len(result) == 1
    assert result[0]["tender_id"] == tender_a
```

```python
# tests/integration/test_execution_ledger_api.py -- add these tests (reuses
# this file's existing fixtures from Task 6)
async def test_execution_summary_reports_the_delta(client, pm_user, tender_with_boq_and_lock_in, engine):
    from packages.decision.execution_fact_model import ExecutionFact
    from packages.decision.execution_ledger_store import store_execution_fact

    async with engine.begin() as conn:
        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_with_boq_and_lock_in,
                boqline_source_line_id=501,
                planned_qty=Decimal("10"),
                actual_qty=Decimal("15"),
                deviation_reason="more rebar used",
                deviation_category="rework",
                culprit_type="internal",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:1",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    response = await client.get(f"/tenders/{tender_with_boq_and_lock_in}/execution-summary", headers={"X-User": pm_user})
    assert response.status_code == 200
    body = response.json()
    assert body["plan_fact_deltas"][0]["delta"] == "5"
    assert body["deviation_category_counts"]["rework"] == 1


async def test_close_project_persists_overhead_buffer_contributions(client, pm_user, tender_with_boq_and_lock_in, engine):
    from packages.decision.execution_fact_model import ExecutionFact
    from packages.decision.execution_ledger_store import store_execution_fact

    async with engine.begin() as conn:
        await store_execution_fact(
            conn,
            ExecutionFact(
                tender_id=tender_with_boq_and_lock_in,
                boqline_source_line_id=None,
                planned_qty=None,
                actual_qty=None,
                deviation_reason="site handover delayed",
                deviation_category="preliminaries",
                culprit_type="customer",
                culprit_vendor_name=None,
                culprit_vendor_id=None,
                evidence_source="napkin-ocr:2",
                observed_at="2026-08-10T00:00:00+00:00",
            ),
        )

    response = await client.post(f"/tenders/{tender_with_boq_and_lock_in}/close-project", headers={"X-User": pm_user})
    assert response.status_code == 200
    assert response.json()["deviation_category_counts"]["preliminaries"] == 1

    async with engine.begin() as conn:
        rows = (
            (
                await conn.execute(
                    text("SELECT deviation_category, fact_count FROM overhead_buffer_contributions WHERE tender_id = :t"),
                    {"t": tender_with_boq_and_lock_in},
                )
            )
            .mappings()
            .all()
        )
    assert any(r["deviation_category"] == "preliminaries" and r["fact_count"] == 1 for r in rows)
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/unit/test_execution_ledger_summary.py -q` — expected FAIL (`ModuleNotFoundError`).
Run: `python -m pytest tests/integration/test_execution_ledger_store.py tests/integration/test_execution_ledger_api.py -q` — expected FAIL (new functions/routes don't exist).

- [ ] **Step 3: Implement**

Add to `migrations/0016_execution_ledger.sql` (append at the end, same migration -- this task's schema addition belongs with the rest of task 4.C's schema, not a separate migration number, since it hasn't been applied/released yet):

```sql
-- Project closure output (P318's "вклад в исторический буфер накладных"):
-- a RAW COUNT per deviation_category, not a cost-weighted adjustment -- the
-- formula that turns this into an actual estimate overlay is Phase 4.D's
-- calibration loop (TENDER_INTELLIGENCE_SPEC.md Section7.4, P319), not built
-- here. Append-only, same discipline as execution_facts.
CREATE TABLE overhead_buffer_contributions (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    deviation_category TEXT NOT NULL CHECK (deviation_category IN ('preliminaries', 'downtime', 'rework', 'last_mile')),
    fact_count INTEGER NOT NULL,
    contributed_at TIMESTAMPTZ NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX overhead_buffer_contributions_tender_idx ON overhead_buffer_contributions (tender_id);
```

(If Task 2's migration file was already committed in an earlier step of this same plan run, append this block to that same `migrations/0016_execution_ledger.sql` file with a follow-up commit in this task rather than creating `0017` -- this whole plan is one release unit that has not shipped yet. Only create a new migration number if `0016` has already been merged to `master` by the time this task starts.)

Create `packages/decision/execution_ledger_summary.py`:

```python
"""Pure plan/fact rollup for one tender's ExecutionFacts (Phase 4, task
4.C, TENDER_INTELLIGENCE_SPEC.md Section7.3, P318's "дельта план/факт по
строкам" and "вклад в исторический буфер накладных"). No DB access -- the
route/job that calls this already has the fact list from
execution_ledger_store.list_execution_facts_by_tender."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from .execution_fact_model import DEVIATION_CATEGORIES


@dataclass(frozen=True)
class PlanFactDelta:
    boqline_source_line_id: int
    planned_qty: Decimal
    actual_qty: Decimal
    delta: Decimal


def summarize_plan_fact_deltas(facts: list[dict[str, Any]]) -> tuple[PlanFactDelta, ...]:
    deltas = [
        PlanFactDelta(
            boqline_source_line_id=f["boqline_source_line_id"],
            planned_qty=f["planned_qty"],
            actual_qty=f["actual_qty"],
            delta=f["actual_qty"] - f["planned_qty"],
        )
        for f in facts
        if f["boqline_source_line_id"] is not None and f["planned_qty"] is not None and f["actual_qty"] is not None
    ]
    return tuple(sorted(deltas, key=lambda d: d.boqline_source_line_id))


def summarize_deviation_category_counts(facts: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for f in facts:
        category = f["deviation_category"]
        if category is None:
            continue
        assert category in DEVIATION_CATEGORIES
        counts[category] = counts.get(category, 0) + 1
    return counts
```

In `packages/decision/execution_ledger_store.py`, add:

```python
async def store_overhead_buffer_contribution(
    conn: AsyncConnection, *, tender_id: int, deviation_category: str, fact_count: int, contributed_at: str
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO overhead_buffer_contributions (tender_id, deviation_category, fact_count, contributed_at)
                VALUES (:tender_id, :deviation_category, :fact_count, :contributed_at)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "deviation_category": deviation_category,
                "fact_count": fact_count,
                "contributed_at": contributed_at,
            },
        )
    ).scalar_one()


async def list_execution_facts_by_organization_voen(conn: AsyncConnection, *, organization_voen: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT ef.id, ef.tender_id, ef.boqline_source_line_id, ef.planned_qty, ef.actual_qty,
                           ef.deviation_reason, ef.deviation_category, ef.culprit_type, ef.observed_at
                    FROM execution_facts ef
                    WHERE ef.culprit_type = 'customer'
                      AND ef.tender_id IN (
                        SELECT tender_id FROM (
                            SELECT DISTINCT ON (tender_id) tender_id, normalized_fields
                            FROM tender_versions
                            ORDER BY tender_id, id DESC
                        ) latest
                        WHERE latest.normalized_fields ->> 'organization_voen' = :organization_voen
                      )
                    ORDER BY ef.tender_id, ef.id
                    """
                ),
                {"organization_voen": organization_voen},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]
```

In `apps/api_tender/routers/execution_ledger.py`, add:

```python
from packages.decision.execution_ledger_store import (
    list_execution_facts_by_organization_voen,
    store_overhead_buffer_contribution,
)
from packages.decision.execution_ledger_summary import summarize_deviation_category_counts, summarize_plan_fact_deltas


class PlanFactDeltaResponse(BaseModel):
    boqline_source_line_id: int
    planned_qty: str
    actual_qty: str
    delta: str


class ExecutionSummaryResponse(BaseModel):
    plan_fact_deltas: list[PlanFactDeltaResponse]
    deviation_category_counts: dict[str, int]


async def _build_summary(conn: AsyncConnection, *, tender_id: int) -> ExecutionSummaryResponse:
    facts = await list_execution_facts_by_tender(conn, tender_id=tender_id)
    deltas = summarize_plan_fact_deltas(facts)
    counts = summarize_deviation_category_counts(facts)
    return ExecutionSummaryResponse(
        plan_fact_deltas=[
            PlanFactDeltaResponse(
                boqline_source_line_id=d.boqline_source_line_id,
                planned_qty=str(d.planned_qty),
                actual_qty=str(d.actual_qty),
                delta=str(d.delta),
            )
            for d in deltas
        ],
        deviation_category_counts=counts,
    )


@router.get("/execution-summary", response_model=ExecutionSummaryResponse)
async def get_execution_summary(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.read", get_current_identity)),
) -> ExecutionSummaryResponse:
    return await _build_summary(conn, tender_id=tender_id)


@router.post("/close-project", response_model=ExecutionSummaryResponse)
async def close_project(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.close_project", get_current_identity)),
) -> ExecutionSummaryResponse:
    summary = await _build_summary(conn, tender_id=tender_id)
    contributed_at = datetime.now(UTC).isoformat()
    for category, count in summary.deviation_category_counts.items():
        await store_overhead_buffer_contribution(
            conn, tender_id=tender_id, deviation_category=category, fact_count=count, contributed_at=contributed_at
        )
    await write_audit_log(
        conn,
        actor=identity.subject,
        action="execution_ledger.close_project",
        object_type="tender",
        object_id=str(tender_id),
        object_version=None,
        reason=None,
    )
    return summary


class OrganizationExecutionHistoryResponse(BaseModel):
    items: list[dict[str, Any]]


# get_organization_execution_history spans tenders (it looks up every
# tender sharing one buyer's organization_voen) -- it does not belong on
# `router`, which is prefixed /tenders/{tender_id}. A second, separate
# router carries it instead.
organization_router = APIRouter(prefix="/organizations/{organization_voen}", tags=["execution-ledger"])


@organization_router.get("/execution-history", response_model=OrganizationExecutionHistoryResponse)
async def get_organization_execution_history(
    organization_voen: str,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.execution_facts.read", get_current_identity)),
) -> OrganizationExecutionHistoryResponse:
    items = await list_execution_facts_by_organization_voen(conn, organization_voen=organization_voen)
    return OrganizationExecutionHistoryResponse(items=items)
```

In `apps/api_tender/main.py`, Task 6 already imports the whole `execution_ledger` module (`from .routers import admin_users, decision, execution_ledger, health`), so no import change is needed here -- just add one more `include_router` line for the second router, right after Task 6's:
```python
    app.include_router(execution_ledger.router)
    app.include_router(execution_ledger.organization_router)
    return app
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/unit/test_execution_ledger_summary.py tests/integration/test_execution_ledger_store.py tests/integration/test_execution_ledger_api.py -q` — expected PASS.
Run: `python -m pytest tests/ -q -m "not live_network"` — full regression check.
Run: `python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py`

- [ ] **Step 5: Commit**

```bash
git add migrations/0016_execution_ledger.sql packages/decision/execution_ledger_summary.py packages/decision/execution_ledger_store.py apps/api_tender/routers/execution_ledger.py apps/api_tender/main.py tests/unit/test_execution_ledger_summary.py tests/integration/test_execution_ledger_store.py tests/integration/test_execution_ledger_api.py
git commit -m "feat(decision,api-tender): project closure summary, overhead buffer contribution, buyer execution history (task 4.C)"
```

---

## Deferred (record in `docs/decisions/OPEN-QUESTIONS.md` at close-out, do not build here)

- Voice-note transcription (ASR) — same open tech-choice gap task 3.A already recorded; `execution_napkin_evidence` accepts and stores `'voice'` captures today but nothing parses them.
- The overhead-buffer *application* (turning `overhead_buffer_contributions` counts into an actual cost overlay on a new 4.A estimate) is Phase 4.D's calibration loop, P319 — this task only produces the raw counts to consume later.
- `D-VND-REP`'s trust-coefficient formula remains untouched — the vendor reputation feed built here only appends typed facts, exactly like the existing `has_positive_reputation`/`has_negative_reputation` booleans it feeds.
- No automatic linkage from `execution-history` back into `GoNoGoInputs.customer_reputation_notes` — ADR-0005 human authority means a human reads the history and writes their own assessment; this task does not auto-populate that free-text field.
- `TBD-TIS-01` (exact TTL numbers per fact class, INV-17) is still unresolved — `reputation_ttl_days` on the napkin submission route has no default, and an unsupplied value queues the fact for human resolution instead of posting it. No end-to-end integration test in this plan drives a real vendor-culprit fact through OCR to a successful reputation post (the same honest gap `packages/vendor`'s own napkin ingestion already has — proven at the unit/contract level, not wired into a real end-to-end HTTP flow with a live OCR backend).
