# Phase 2, Task 2.A — BOQ Line Depth Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Decompose a fetched BOQ page's raw `items` into atomic, typed BOQ line rows — with unit canonicalization, preliminaries/provisional-sum/prime-cost typing, and hidden spec-requirement extraction — so `boq_import` moves from "page ingested" to "line ready for matching/calculation" (`TENDER_INTELLIGENCE_SPEC.md` §5.1, regression **P308**).

**Architecture:** Pure domain logic (unit canonicalization, line-type classification, spec-requirement extraction, line-model assembly) lives in a new dependency-free module (`packages/tender/boq_line_model.py`), testable without a database. A thin persistence module (`packages/tender/boq_lines_store.py`) writes the assembled lines with plain `text()` SQL, matching every other `packages/tender/*` module's style — no ORM. `packages/tender/bom_lines_job.py`'s existing `process_bom_lines_page` calls both, once per page, after a normalized version already exists for that page — reusing the pipeline's existing raw-snapshot-first, schema-drift-gated flow rather than adding a parallel one. Per-item shape (not just page-level shape) is now schema-drift-checked too, closing a real gap: today `detect_schema_drift` only inspects page-level fields, never validates what is inside the `items` array.

**Tech Stack:** Python 3.12, stdlib `re`/`decimal`, SQLAlchemy Core `text()` + asyncpg (existing stack, no new dependency), pytest/pytest-asyncio, real captured fixtures under `fixtures/tender-snapshots/etender/`.

## Global Constraints

- Python `>=3.12`, `from __future__ import annotations` at the top of every new/modified module (existing convention across `packages/tender/*`).
- `ruff` line-length 130, rules `E, F, I, UP, B, C4, RUF` (`pyproject.toml`); run `python -m ruff format --check .` and `python -m ruff check .` before considering any task done.
- `mypy packages apps` must report zero issues (`ignore_missing_imports = true`, `warn_unused_ignores = true`, `warn_redundant_casts = true`).
- `python tools/check_v1_untouched.py` must PASS after every task (stdlib-only, no deps).
- No ORM: every DB module in `packages/tender/` uses SQLAlchemy `text()` with named params, mirroring `normalized.py`/`boq_completeness.py`/`raw_snapshot.py`.
- `Decimal` (not `float`) for any quantity/rate/amount that could feed downstream calculation — this codebase already treats numeric procurement data as something that must not silently lose precision.
- No invented data: a field the real captured contract does not provide (e.g. no per-line `rate`/`amount` in any of the three captured BOQ fixture pages) stays `None`, never a fabricated default (`AGENTS.md` hard ban #3, `INV-11`).
- No invented vocabulary: line-type keyword matching and "or equivalent" detection are implemented **only** for the terms the spec itself names (English `preliminaries`/`provisional sum`/`prime cost`; Russian «или эквивалент» from `TENDER_INTELLIGENCE_SPEC.md` §5.1 verbatim) plus the source data's own language (Azerbaijani `və ya` + `ekvivalent`) — Azerbaijani/Russian equivalents for `preliminaries`/`provisional sum`/`prime cost` are **not** implemented in this plan because no source document supplies them; Task 11 records this as an explicit, non-blocking open question rather than a silent gap.
- Traceability: every commit message in this plan's steps references `FR-TND-*`/`P308`/`INT-02` as applicable, per `AGENTS.md` §6.
- Migration numbering continues from `0006_exception_queue.sql` → `0007_boq_lines.sql` (`migrations/README.md` §Rules 3/7: versioned, never renumbered).

## Ground truth from the real fixtures (do not re-derive, just reuse)

Verified directly against `fixtures/tender-snapshots/etender/event_355920_bomlines_page{1,2,3}.raw.json` (4135-line/42-page real BOQ, per `MANIFEST.md`):

- Every item across all 3 real pages has **exactly** these 6 keys, no more, no less: `id`, `name`, `description`, `unitOfMeasure`, `quantity`, `categoryCode`. No `rate`, no `amount`, no hierarchical line `code`.
- `categoryCode` is constant (`"72121403"`) across every item on every page in this fixture — it is a UNSPSC-style classification code, not a distinguishing per-line identifier. It is still the only real field that maps to the spec's `code` concept, so it is used as-is (real data, not invented), but Task 5's line-model docstring must say plainly that `code` may be non-distinguishing / constant for a given source page, not imply per-line uniqueness that isn't there.
- `unitOfMeasure` observed values across all 3 pages: `ədəd` (Azerbaijani "piece"), `m` (metre), `dəst` (Azerbaijani "set") — nothing else.
- `quantity` is **not always an integer** — `event_355920_bomlines_page2.raw.json` has one item with `quantity: 11.5`. Confirms `Decimal`, not `int`, is required.
- None of the 3 real pages contain any preliminaries/provisional-sum/prime-cost line, nor any concrete-grade (`B25`/`B30`), rebar-class, or `AZS`/`GOST`/`EN` standard reference, nor an explicit "or equivalent" phrase — this is a real electrical-works BOQ, not a concrete-works one. **Consequence for P308 (recorded again in Task 10, don't let it get lost):** the "preliminaries/provisional marked by type" and "spec requirements linked to line" halves of P308's acceptance text can only be proven end-to-end against a realistic-but-constructed line for now — not against this specific real fixture, which genuinely contains neither. The "every real line has unit+qty" half of P308 **is** proven against real data. Task 10's test makes this split explicit rather than blurring a constructed-data proof into a claim of real-data proof.

## File Structure

**Create:**
- `packages/tender/boq_line_model.py` — pure logic: `CanonicalUnit`, `canonicalize_unit()`, `SpecRequirement`, `extract_spec_requirements()`, `classify_line_type()`, `BoqLine`, `build_boq_lines()`. No DB import.
- `packages/tender/boq_lines_store.py` — `store_boq_lines()`, the only module in this plan that touches `boq_lines` via SQL.
- `migrations/0007_boq_lines.sql` — new `boq_lines` table.
- `tests/unit/test_boq_line_model.py` — pure-logic tests (Fast gate, no Docker needed).
- `tests/unit/test_schema_drift_over_items.py` — pure-logic test for the new aggregate item-drift helper.
- `tests/integration/test_boq_lines_storage.py` — DB round-trip tests for `store_boq_lines` against the real page-1 fixture.
- `tests/integration/test_bom_line_item_drift.py` — item-level drift detection wired into `ingest_bom_lines_page`.

**Modify:**
- `packages/tender/schema_drift.py` — add `detect_schema_drift_over_items()`.
- `packages/tender/etender_contract.py` — add `BOM_LINE_ITEM_CONTRACT`.
- `packages/tender/etender_connector.py` — `_ingest()` gains optional item-drift checking; `ingest_bom_lines_page()` passes `BOM_LINE_ITEM_CONTRACT`.
- `packages/tender/bom_lines_job.py` — `process_bom_lines_page()` calls `build_boq_lines()` + `store_boq_lines()` after a page ingests cleanly, and reports `boq_lines_stored` in the returned checkpoint dict.
- `tests/integration/test_bom_lines_pagination.py` — existing assertions extended to also check `boq_lines` row counts (the existing 3-page real-pagination test is the natural place; it already drives all 3 real pages end-to-end).
- `packages/tender/README.md` — replace the stale "Not implemented yet" line.
- `docs/reports/WORKLOG.md` — append-only entry for this task (`AGENTS.md` §4).
- `docs/decisions/OPEN-QUESTIONS.md` — append-only entry recording the non-English keyword-vocabulary gap (see Global Constraints).

**Interfaces produced (for later tasks / later phases to consume):**
- `boq_line_model.BoqLine` — frozen dataclass, fields: `source_line_id: int`, `page_number: int`, `section: str | None`, `category_code: str | None`, `description: str`, `unit_raw: str`, `unit_canonical: str | None`, `unit_status: str`, `qty: Decimal`, `line_type: str`, `spec_requirements: tuple[SpecRequirement, ...]`, `rate: Decimal | None`, `amount: Decimal | None`.
- `boq_line_model.build_boq_lines(*, page_number: int, items: list[dict[str, Any]]) -> list[BoqLine]`.
- `boq_lines_store.store_boq_lines(conn, *, source: str, event_id: int, tender_version_id: int, raw_snapshot_id: int, lines: list[BoqLine]) -> int` (returns count inserted).
- `schema_drift.detect_schema_drift_over_items(item_contract: SourceContract, items: list[dict]) -> SchemaDrift`.

---

### Task 1: `boq_lines` migration

**Files:**
- Create: `migrations/0007_boq_lines.sql`
- Test: `tests/integration/test_boq_lines_migration.py`

**Interfaces:**
- Produces: table `boq_lines` with columns `id, source, event_id, page_number, tender_version_id, raw_snapshot_id, source_line_id, section, category_code, description, unit_raw, unit_canonical, unit_status, qty, line_type, spec_requirements, rate, amount, created_at`, unique on `(source, event_id, source_line_id)`.

- [ ] **Step 1: Write the migration file**

```sql
-- Atomic BOQ line rows (FR-TND-*, TENDER_INTELLIGENCE_SPEC.md §5.1, P308):
-- one row per source BOQ item, with unit canonicalization status, line-type
-- classification, and extracted hidden spec requirements attached. A page
-- that fails item-level schema drift never reaches this table (see
-- etender_connector.py) -- there is no partial/guessed row for a page whose
-- item shape the connector doesn't recognize.

CREATE TABLE boq_lines (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    event_id BIGINT NOT NULL,
    page_number INTEGER NOT NULL,
    tender_version_id BIGINT NOT NULL REFERENCES tender_versions (id),
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    source_line_id BIGINT NOT NULL,
    section TEXT,
    category_code TEXT,
    description TEXT NOT NULL,
    unit_raw TEXT NOT NULL,
    unit_canonical TEXT,
    unit_status TEXT NOT NULL CHECK (unit_status IN ('mapped', 'unmapped')),
    qty NUMERIC NOT NULL,
    line_type TEXT NOT NULL DEFAULT 'normal'
        CHECK (line_type IN ('normal', 'preliminaries', 'provisional_sum', 'prime_cost')),
    spec_requirements JSONB NOT NULL DEFAULT '[]'::jsonb,
    rate NUMERIC,
    amount NUMERIC,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, event_id, source_line_id)
);

CREATE INDEX boq_lines_event_idx ON boq_lines (source, event_id);
```

- [ ] **Step 2: Write the failing test**

```python
"""FR-TND-*, P308: boq_lines table exists with the expected shape and
uniqueness guard (one row per real source line id, never a silent
duplicate on reprocessing)."""

from __future__ import annotations

from sqlalchemy import text


async def test_boq_lines_table_has_expected_columns(engine):
    async with engine.begin() as conn:
        columns = (
            (
                await conn.execute(
                    text("SELECT column_name FROM information_schema.columns WHERE table_name = 'boq_lines' ORDER BY column_name")
                )
            )
            .scalars()
            .all()
        )
    expected = {
        "id",
        "source",
        "event_id",
        "page_number",
        "tender_version_id",
        "raw_snapshot_id",
        "source_line_id",
        "section",
        "category_code",
        "description",
        "unit_raw",
        "unit_canonical",
        "unit_status",
        "qty",
        "line_type",
        "spec_requirements",
        "rate",
        "amount",
        "created_at",
    }
    assert expected.issubset(set(columns))


async def test_boq_lines_rejects_duplicate_source_line_id_for_same_event(engine):
    async with engine.begin() as conn:
        tender_id = (
            await conn.execute(text("INSERT INTO tenders (source, identity_key) VALUES ('etender', 'x') RETURNING id"))
        ).scalar_one()
        version_id = (
            await conn.execute(
                text(
                    "INSERT INTO tender_versions (tender_id, version_number, raw_snapshot_id, parser_version, normalized_fields) "
                    "VALUES (:tid, 1, :rsid, 'etender-v1', '{}'::jsonb) RETURNING id"
                ),
                {"tid": tender_id, "rsid": await _insert_raw_snapshot(conn)},
            )
        ).scalar_one()
        await conn.execute(
            text(
                "INSERT INTO boq_lines (source, event_id, page_number, tender_version_id, raw_snapshot_id, "
                "source_line_id, description, unit_raw, unit_status, qty) "
                "VALUES ('etender', 1, 1, :vid, :vid, 999, 'a line', 'ədəd', 'mapped', 1)"
            ),
            {"vid": version_id},
        )
        raised = False
        try:
            await conn.execute(
                text(
                    "INSERT INTO boq_lines (source, event_id, page_number, tender_version_id, raw_snapshot_id, "
                    "source_line_id, description, unit_raw, unit_status, qty) "
                    "VALUES ('etender', 1, 1, :vid, :vid, 999, 'a duplicate line', 'ədəd', 'mapped', 1)"
                ),
                {"vid": version_id},
            )
        except Exception:
            raised = True
        assert raised is True


async def _insert_raw_snapshot(conn) -> int:
    return (
        await conn.execute(
            text(
                "INSERT INTO raw_snapshots (source, resource_type, identity_key, checksum, body, contract_version, correlation_id) "
                "VALUES ('etender', 'etender.bom_lines_page', 'k', 'c', '{}'::jsonb, 'v', 'corr') RETURNING id"
            )
        )
    ).scalar_one()
```

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_boq_lines_migration.py -v`
Expected: FAIL — `relation "boq_lines" does not exist` (migration not applied yet, since the file doesn't exist).

- [ ] **Step 4: Confirm the migration file makes it pass**

The `engine` fixture (`tests/conftest.py`) applies every `.sql` file under `migrations/` automatically for each test — no separate registration step is needed. Re-run the same command.

Run: `python -m pytest tests/integration/test_boq_lines_migration.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add migrations/0007_boq_lines.sql tests/integration/test_boq_lines_migration.py
git commit -m "feat(tender): add boq_lines table (FR-TND-*, P308 prerequisite)"
```

---

### Task 2: Unit canonicalization

**Files:**
- Create: `packages/tender/boq_line_model.py`
- Test: `tests/unit/test_boq_line_model.py`

**Interfaces:**
- Produces: `CanonicalUnit(raw: str, canonical: str | None, status: str)`, `canonicalize_unit(raw_unit: str) -> CanonicalUnit`.

- [ ] **Step 1: Write the failing test**

```python
"""FR-TND-*: unit canonicalization never guesses -- an unmapped unit keeps
its raw string and is flagged 'unmapped', not silently coerced to a wrong
canonical unit (INV-11 no silent fallback)."""

from __future__ import annotations

from packages.tender.boq_line_model import canonicalize_unit


def test_canonicalizes_real_captured_units():
    # These three are the only unitOfMeasure values observed across all
    # three real captured pages of event 355920 (see MANIFEST.md).
    assert canonicalize_unit("ədəd") == ("pcs", "mapped")
    assert canonicalize_unit("m") == ("m", "mapped")
    assert canonicalize_unit("dəst") == ("set", "mapped")


def test_canonicalizes_other_unambiguous_construction_units():
    assert canonicalize_unit("kg") == ("kg", "mapped")
    assert canonicalize_unit("m2") == ("m2", "mapped")
    assert canonicalize_unit("m3") == ("m3", "mapped")


def test_unmapped_unit_keeps_raw_string_and_is_flagged_not_guessed():
    result = canonicalize_unit("qutu")  # "box" -- not in the canonical map
    assert result.canonical is None
    assert result.status == "unmapped"
    assert result.raw == "qutu"


def test_canonicalize_unit_helper_returns_dataclass():
    from packages.tender.boq_line_model import CanonicalUnit

    result = canonicalize_unit("m")
    assert isinstance(result, CanonicalUnit)
```

Note: the tuple-equality assertions above rely on `CanonicalUnit` being comparable to a 3-tuple via `__eq__`; since it is a plain `@dataclass(frozen=True)`, dataclass instances do **not** equal plain tuples. Write the test against named fields instead — replace the first two test bodies' assertions with:

```python
def test_canonicalizes_real_captured_units():
    assert canonicalize_unit("ədəd") == CanonicalUnit(raw="ədəd", canonical="pcs", status="mapped")
    assert canonicalize_unit("m") == CanonicalUnit(raw="m", canonical="m", status="mapped")
    assert canonicalize_unit("dəst") == CanonicalUnit(raw="dəst", canonical="set", status="mapped")
```

(add `from packages.tender.boq_line_model import CanonicalUnit, canonicalize_unit` at the top of the test file instead of importing it only inside one test function).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.boq_line_model'`

- [ ] **Step 3: Write minimal implementation**

```python
"""Atomic BOQ line model (FR-TND-*, TENDER_INTELLIGENCE_SPEC.md §5.1, P308).

Pure functions only -- no DB import in this module. `build_boq_lines`
assembles one `BoqLine` per source item; persistence is
`boq_lines_store.store_boq_lines`, kept separate so this module's logic is
testable without Postgres.

Unit canonicalization only maps units actually observed in real captured
fixtures (see MANIFEST.md) plus a handful of unambiguous SI/construction
units (m2, m3, kg, t, l) certain to appear in any BOQ. An unrecognized unit
is never guessed at -- it is flagged `unmapped` and the raw string is kept,
so a downstream matching/calculation step can see exactly which lines have
an unresolved unit rather than silently trusting a wrong canonicalization
(INV-11)."""

from __future__ import annotations

from dataclasses import dataclass

_UNIT_CANONICAL_MAP: dict[str, str] = {
    "ədəd": "pcs",  # Azerbaijani "piece" -- observed on all 3 real captured pages
    "dəst": "set",  # Azerbaijani "set" -- observed on real captured page 3
    "m": "m",
    "m2": "m2",
    "m²": "m2",
    "m3": "m3",
    "m³": "m3",
    "kg": "kg",
    "t": "t",
    "l": "l",
}


@dataclass(frozen=True)
class CanonicalUnit:
    raw: str
    canonical: str | None
    status: str  # "mapped" | "unmapped"


def canonicalize_unit(raw_unit: str) -> CanonicalUnit:
    canonical = _UNIT_CANONICAL_MAP.get(raw_unit)
    status = "mapped" if canonical is not None else "unmapped"
    return CanonicalUnit(raw=raw_unit, canonical=canonical, status=status)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/boq_line_model.py tests/unit/test_boq_line_model.py
git commit -m "feat(tender): BOQ unit canonicalization, unmapped units flagged not guessed (FR-TND-*)"
```

---

### Task 3: Line-type classification (preliminaries / provisional sum / prime cost)

**Files:**
- Modify: `packages/tender/boq_line_model.py`
- Modify: `tests/unit/test_boq_line_model.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `classify_line_type(name: str, description: str) -> str`, one of `"normal" | "preliminaries" | "provisional_sum" | "prime_cost"`.

- [ ] **Step 1: Write the failing tests**

```python
from packages.tender.boq_line_model import classify_line_type


def test_classifies_preliminaries_by_keyword():
    assert classify_line_type("Preliminaries", "Site preliminaries and general conditions") == "preliminaries"


def test_classifies_provisional_sum_by_keyword():
    assert classify_line_type("General", "Provisional sum for unforeseen ground conditions") == "provisional_sum"
    assert classify_line_type("General", "Provisional sums for utility connections") == "provisional_sum"


def test_classifies_prime_cost_by_keyword():
    assert classify_line_type("General", "Prime cost sum for lift installation") == "prime_cost"
    assert classify_line_type("General", "PC sum: sanitary fittings") == "prime_cost"


def test_defaults_to_normal_for_an_ordinary_line():
    # Real line from event_355920_bomlines_page1.raw.json -- must not be
    # misclassified just because it mentions a device/cabinet.
    assert (
        classify_line_type(
            "Əsas korpus - Elektrik təchizatı və güc avadanlıqı (Blok A1-A2)",
            "Metal şkaf 800x600x250mm",
        )
        == "normal"
    )


def test_classification_is_case_insensitive():
    assert classify_line_type("x", "PRELIMINARIES") == "preliminaries"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'classify_line_type'`

- [ ] **Step 3: Write minimal implementation**

Append to `packages/tender/boq_line_model.py`:

```python
import re

# Keyword sets are deliberately English-only, matching the exact terms
# TENDER_INTELLIGENCE_SPEC.md §5.1 names ("preliminaries", "provisional
# sums", "prime cost"). No Azerbaijani/Russian equivalents are guessed at
# here -- none are supplied by any source document, and inventing a
# translation would be exactly the kind of unsourced fact AGENTS.md hard
# ban #2 forbids. See docs/decisions/OPEN-QUESTIONS.md (2026-08-05, task
# 2.A entry) for the resulting open question to the owner.
_PRELIMINARIES_RE = re.compile(r"\bpreliminar(?:y|ies)\b", re.IGNORECASE)
_PROVISIONAL_SUM_RE = re.compile(r"\bprovisional\s+sums?\b", re.IGNORECASE)
_PRIME_COST_RE = re.compile(r"\bprime\s+cost\b|\bPC\s+sum\b", re.IGNORECASE)


def classify_line_type(name: str, description: str) -> str:
    text = f"{name} {description}"
    if _PRELIMINARIES_RE.search(text):
        return "preliminaries"
    if _PROVISIONAL_SUM_RE.search(text):
        return "provisional_sum"
    if _PRIME_COST_RE.search(text):
        return "prime_cost"
    return "normal"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: PASS (10 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/boq_line_model.py tests/unit/test_boq_line_model.py
git commit -m "feat(tender): classify BOQ lines as preliminaries/provisional_sum/prime_cost (P308)"
```

---

### Task 4: Hidden spec-requirement extraction

**Files:**
- Modify: `packages/tender/boq_line_model.py`
- Modify: `tests/unit/test_boq_line_model.py`

**Interfaces:**
- Produces: `SpecRequirement(kind: str, raw_text: str)`, `extract_spec_requirements(description: str) -> tuple[SpecRequirement, ...]`. `kind` is one of `"concrete_grade" | "rebar_class" | "standard_reference" | "or_equivalent"`.

- [ ] **Step 1: Write the failing tests**

```python
from packages.tender.boq_line_model import SpecRequirement, extract_spec_requirements


def test_extracts_concrete_grade():
    reqs = extract_spec_requirements("Beton B25 tökülməsi, qalınlığı 200mm")
    assert SpecRequirement(kind="concrete_grade", raw_text="B25") in reqs


def test_extracts_marka_style_concrete_grade():
    reqs = extract_spec_requirements("Beton M300 markalı")
    assert SpecRequirement(kind="concrete_grade", raw_text="M300") in reqs


def test_extracts_standard_reference_azs():
    reqs = extract_spec_requirements("AZS 1234-2020 standartına uyğun")
    assert SpecRequirement(kind="standard_reference", raw_text="AZS 1234-2020") in reqs


def test_extracts_standard_reference_gost():
    reqs = extract_spec_requirements("ГОСТ 5781 armaturu")
    assert SpecRequirement(kind="standard_reference", raw_text="ГОСТ 5781") in reqs


def test_extracts_standard_reference_en():
    reqs = extract_spec_requirements("cable per EN 60228")
    assert SpecRequirement(kind="standard_reference", raw_text="EN 60228") in reqs


def test_extracts_or_equivalent_russian_phrase_from_spec():
    # Literal phrase TENDER_INTELLIGENCE_SPEC.md §5.1 names.
    reqs = extract_spec_requirements("кабель ВВГ или эквивалент")
    assert any(r.kind == "or_equivalent" for r in reqs)


def test_extracts_or_equivalent_azerbaijani_phrase():
    reqs = extract_spec_requirements("Şkaf və ya ekvivalent")
    assert any(r.kind == "or_equivalent" for r in reqs)


def test_extracts_or_equivalent_english_phrase():
    reqs = extract_spec_requirements("steel cabinet or equivalent")
    assert any(r.kind == "or_equivalent" for r in reqs)


def test_no_false_positive_on_a_plain_real_description():
    # Real description from event_355920_bomlines_page1.raw.json -- no
    # hidden spec requirement of any kind actually present in it.
    reqs = extract_spec_requirements("Cihaz və ya aparatların quraşdırılması")
    # "və ya" appears here but is NOT followed by "ekvivalent" -- must not
    # be flagged as or_equivalent just because "və ya" is present.
    assert reqs == ()


def test_extracts_multiple_requirements_from_one_description():
    reqs = extract_spec_requirements("Beton B30, AZS 5678 standartına uyğun, və ya ekvivalent")
    kinds = {r.kind for r in reqs}
    assert kinds == {"concrete_grade", "standard_reference", "or_equivalent"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'SpecRequirement'`

- [ ] **Step 3: Write minimal implementation**

Append to `packages/tender/boq_line_model.py`:

```python
@dataclass(frozen=True)
class SpecRequirement:
    kind: str  # "concrete_grade" | "rebar_class" | "standard_reference" | "or_equivalent"
    raw_text: str


# Concrete grade: Eurocode-style "B" class (B15..B60) or Soviet/regional
# "marka" style "M" class (M100..M400) -- both are named directly in
# TENDER_INTELLIGENCE_SPEC.md §5.1 ("марка бетона B25/B30"). No other
# concrete-grade notation is implemented until real evidence of one is
# captured.
_CONCRETE_GRADE_RE = re.compile(r"\bB\s?(?:15|20|25|30|35|40|45|50|55|60)\b|\bM\s?(?:100|150|200|250|300|350|400)\b")

# Rebar class: common A-series notations (A-I..A-IV, A400, A500). Best-effort
# pattern set, not an exhaustive locked list -- extend when real evidence
# with a different notation is captured (no source document enumerates the
# full set).
_REBAR_CLASS_RE = re.compile(r"\bA[- ]?(?:I{1,3}|IV|400|500|600)\b")

# Standard reference: AZS / GOST (Latin or Cyrillic) / EN, each followed by
# a number -- exactly the three families TENDER_INTELLIGENCE_SPEC.md §5.1
# names ("стандарт AZS/ГОСТ/EN").
_STANDARD_REFERENCE_RE = re.compile(r"\b(?:AZS|ГОСТ|GOST|EN)\s?\d+(?:[-.]\d+)*\b")

# "Or equivalent": the exact Russian phrase the spec names («или
# эквивалент»), plus its Azerbaijani cognate in the source data's own
# language (used with "və ya", not "ekvivalent" alone -- "ekvivalent" alone
# is too common a loanword to flag by itself) and the English cognate.
_OR_EQUIVALENT_RE = re.compile(
    r"или\s+эквивалент|(?:və\s+ya|ya\s+da)\s+ekvivalent|\bor\s+equivalent\b",
    re.IGNORECASE,
)


def extract_spec_requirements(description: str) -> tuple[SpecRequirement, ...]:
    found: list[SpecRequirement] = []
    for match in _CONCRETE_GRADE_RE.finditer(description):
        found.append(SpecRequirement(kind="concrete_grade", raw_text=match.group(0)))
    for match in _REBAR_CLASS_RE.finditer(description):
        found.append(SpecRequirement(kind="rebar_class", raw_text=match.group(0)))
    for match in _STANDARD_REFERENCE_RE.finditer(description):
        found.append(SpecRequirement(kind="standard_reference", raw_text=match.group(0)))
    for match in _OR_EQUIVALENT_RE.finditer(description):
        found.append(SpecRequirement(kind="or_equivalent", raw_text=match.group(0)))
    return tuple(found)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: PASS (21 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/boq_line_model.py tests/unit/test_boq_line_model.py
git commit -m "feat(tender): extract hidden BOQ spec requirements (concrete grade/rebar/standard/or-equivalent) (P308)"
```

---

### Task 5: `BoqLine` assembly

**Files:**
- Modify: `packages/tender/boq_line_model.py`
- Modify: `tests/unit/test_boq_line_model.py`

**Interfaces:**
- Consumes: `canonicalize_unit`, `classify_line_type`, `extract_spec_requirements` (all from this same file, Tasks 2-4).
- Produces: `BoqLine` dataclass, `build_boq_lines(*, page_number: int, items: list[dict[str, Any]]) -> list[BoqLine]`.

- [ ] **Step 1: Write the failing tests**

```python
from decimal import Decimal

from packages.tender.boq_line_model import BoqLine, build_boq_lines


def test_builds_lines_from_synthetic_items_covering_every_type():
    items = [
        {
            "id": 1,
            "name": "Section A",
            "description": "Preliminaries and site setup",
            "unitOfMeasure": "ədəd",
            "quantity": 1,
            "categoryCode": "999",
        },
        {
            "id": 2,
            "name": "Section A",
            "description": "Beton B25 tökülməsi",
            "unitOfMeasure": "m3",
            "quantity": Decimal("12.5"),
            "categoryCode": "999",
        },
        {
            "id": 3,
            "name": "Section A",
            "description": "Provisional sum for utilities",
            "unitOfMeasure": "qutu",
            "quantity": 1,
            "categoryCode": "999",
        },
    ]
    lines = build_boq_lines(page_number=1, items=items)

    assert len(lines) == 3
    assert all(isinstance(line, BoqLine) for line in lines)

    preliminaries, concrete, provisional = lines
    assert preliminaries.line_type == "preliminaries"
    assert preliminaries.unit_status == "mapped"

    assert concrete.line_type == "normal"
    assert concrete.qty == Decimal("12.5")
    assert concrete.unit_canonical == "m3"
    assert any(r.kind == "concrete_grade" for r in concrete.spec_requirements)

    assert provisional.line_type == "provisional_sum"
    assert provisional.unit_status == "unmapped"  # "qutu" is not in the canonical map
    assert provisional.unit_raw == "qutu"


def test_source_line_id_and_page_number_are_preserved():
    items = [{"id": 42, "name": "S", "description": "d", "unitOfMeasure": "m", "quantity": 1, "categoryCode": "1"}]
    lines = build_boq_lines(page_number=7, items=items)
    assert lines[0].source_line_id == 42
    assert lines[0].page_number == 7


def test_rate_and_amount_absent_from_source_stay_none_never_fabricated():
    # No real captured BOQ item has ever had rate/amount -- confirmed
    # against all 3 fixture pages. build_boq_lines must not invent zeros.
    items = [{"id": 1, "name": "S", "description": "d", "unitOfMeasure": "m", "quantity": 1, "categoryCode": "1"}]
    line = build_boq_lines(page_number=1, items=items)[0]
    assert line.rate is None
    assert line.amount is None


def test_rate_and_amount_used_verbatim_when_source_does_provide_them():
    items = [
        {
            "id": 1,
            "name": "S",
            "description": "d",
            "unitOfMeasure": "m",
            "quantity": 1,
            "categoryCode": "1",
            "rate": 10,
            "amount": 10,
        }
    ]
    line = build_boq_lines(page_number=1, items=items)[0]
    assert line.rate == Decimal("10")
    assert line.amount == Decimal("10")


def test_builds_lines_from_real_page_1_fixture():
    import json
    from pathlib import Path

    fixture = (
        Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender" / "event_355920_bomlines_page1.raw.json"
    )
    payload = json.loads(fixture.read_bytes())

    lines = build_boq_lines(page_number=1, items=payload["items"])

    assert len(lines) == payload["itemsInPage"] == 100
    for line in lines:
        assert line.qty > 0
        assert line.unit_raw in ("ədəd", "m")
        assert line.category_code == "72121403"
        # Honest real-data assertion (see plan's "Ground truth" section):
        # this specific real fixture contains zero preliminaries/provisional/
        # prime-cost lines -- every line is genuinely "normal" here.
        assert line.line_type == "normal"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: FAIL with `ImportError: cannot import name 'BoqLine'`

- [ ] **Step 3: Write minimal implementation**

Append to `packages/tender/boq_line_model.py` (add `from decimal import Decimal` and `from typing import Any` to the imports at the top):

```python
@dataclass(frozen=True)
class BoqLine:
    source_line_id: int
    page_number: int
    section: str | None
    category_code: str | None
    description: str
    unit_raw: str
    unit_canonical: str | None
    unit_status: str
    qty: Decimal
    line_type: str
    spec_requirements: tuple[SpecRequirement, ...]
    rate: Decimal | None
    amount: Decimal | None


def _to_decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def build_boq_lines(*, page_number: int, items: list[dict[str, Any]]) -> list[BoqLine]:
    lines: list[BoqLine] = []
    for item in items:
        unit = canonicalize_unit(item["unitOfMeasure"])
        lines.append(
            BoqLine(
                source_line_id=item["id"],
                page_number=page_number,
                section=item.get("name"),
                category_code=item.get("categoryCode"),
                description=item["description"],
                unit_raw=unit.raw,
                unit_canonical=unit.canonical,
                unit_status=unit.status,
                qty=Decimal(str(item["quantity"])),
                line_type=classify_line_type(item.get("name", ""), item["description"]),
                spec_requirements=extract_spec_requirements(item["description"]),
                rate=_to_decimal_or_none(item.get("rate")),
                amount=_to_decimal_or_none(item.get("amount")),
            )
        )
    return lines
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_boq_line_model.py -v`
Expected: PASS (26 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/boq_line_model.py tests/unit/test_boq_line_model.py
git commit -m "feat(tender): assemble atomic BoqLine rows from a fetched page's items (P308)"
```

---

### Task 6: Persist BOQ lines

**Files:**
- Create: `packages/tender/boq_lines_store.py`
- Create: `tests/integration/test_boq_lines_storage.py`

**Interfaces:**
- Consumes: `BoqLine` (Task 5).
- Produces: `store_boq_lines(conn, *, source: str, event_id: int, tender_version_id: int, raw_snapshot_id: int, lines: list[BoqLine]) -> int`.

- [ ] **Step 1: Write the failing test**

```python
"""FR-TND-*, P308: atomic BOQ lines persisted with unit/type/spec metadata,
traceable back to the exact raw snapshot and normalized version they came
from (same traceability discipline as tender_versions -> raw_snapshots)."""

from __future__ import annotations

import json
from decimal import Decimal
from pathlib import Path

from sqlalchemy import text

from packages.tender.boq_line_model import build_boq_lines
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


async def _setup_version(conn, *, correlation_id: str) -> tuple[int, int]:
    raw_body = (FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type="etender.bom_lines_page",
        identity_key="etender.bom_lines_page|event_id=355920&PageNumber=1",
        raw_body=raw_body,
        contract_version="etender.bom_lines_page",
        correlation_id=correlation_id,
    )
    tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"boq-lines-test|{correlation_id}")
    version = await create_normalized_version(
        conn,
        tender_id=tender_id,
        raw_snapshot_id=snapshot_id,
        parser_version="etender-v1",
        normalized_fields={},
    )
    return version.id, snapshot_id


async def test_stores_all_lines_from_real_page_1(engine):
    raw_body = (FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    lines = build_boq_lines(page_number=1, items=payload["items"])

    async with engine.begin() as conn:
        version_id, snapshot_id = await _setup_version(conn, correlation_id="corr-store-1")
        inserted = await store_boq_lines(
            conn,
            source="etender",
            event_id=355920,
            tender_version_id=version_id,
            raw_snapshot_id=snapshot_id,
            lines=lines,
        )

    assert inserted == 100

    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text(
                        "SELECT description, unit_raw, unit_canonical, unit_status, qty, line_type, category_code "
                        "FROM boq_lines WHERE source_line_id = 5131448 AND event_id = 355920"
                    )
                )
            )
            .mappings()
            .one()
        )
    assert row["unit_raw"] == "ədəd"
    assert row["unit_canonical"] == "pcs"
    assert row["unit_status"] == "mapped"
    assert row["qty"] == Decimal("1")
    assert row["line_type"] == "normal"
    assert row["category_code"] == "72121403"


async def test_stored_lines_trace_back_to_their_raw_snapshot_and_version(engine):
    raw_body = (FIXTURES / "event_355920_bomlines_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    lines = build_boq_lines(page_number=1, items=payload["items"])[:1]

    async with engine.begin() as conn:
        version_id, snapshot_id = await _setup_version(conn, correlation_id="corr-store-2")
        await store_boq_lines(
            conn,
            source="etender",
            event_id=355920,
            tender_version_id=version_id,
            raw_snapshot_id=snapshot_id,
            lines=lines,
        )

    async with engine.begin() as conn:
        row = (
            (await conn.execute(text("SELECT tender_version_id, raw_snapshot_id FROM boq_lines WHERE event_id = 355920")))
            .mappings()
            .one()
        )
    assert row["tender_version_id"] == version_id
    assert row["raw_snapshot_id"] == snapshot_id
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_boq_lines_storage.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.boq_lines_store'`

- [ ] **Step 3: Write minimal implementation**

```python
"""BOQ line persistence (FR-TND-*, P308). One INSERT per BoqLine, in the
caller's own transaction -- no ON CONFLICT/upsert here: `boq_lines`' unique
constraint on (source, event_id, source_line_id) is a real invariant guard,
and a violation should surface as a genuine error rather than being
silently absorbed (the job-loop transaction wrapping this already
guarantees a page's lines are only durably stored if the whole page's
processing commits, so a legitimate duplicate insert should not happen in
normal operation)."""

from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .boq_line_model import BoqLine


async def store_boq_lines(
    conn: AsyncConnection,
    *,
    source: str,
    event_id: int,
    tender_version_id: int,
    raw_snapshot_id: int,
    lines: list[BoqLine],
) -> int:
    for line in lines:
        await conn.execute(
            text(
                """
                INSERT INTO boq_lines
                    (source, event_id, page_number, tender_version_id, raw_snapshot_id, source_line_id,
                     section, category_code, description, unit_raw, unit_canonical, unit_status, qty,
                     line_type, spec_requirements, rate, amount)
                VALUES
                    (:source, :event_id, :page_number, :tender_version_id, :raw_snapshot_id, :source_line_id,
                     :section, :category_code, :description, :unit_raw, :unit_canonical, :unit_status, :qty,
                     :line_type, CAST(:spec_requirements AS jsonb), :rate, :amount)
                """
            ),
            {
                "source": source,
                "event_id": event_id,
                "page_number": line.page_number,
                "tender_version_id": tender_version_id,
                "raw_snapshot_id": raw_snapshot_id,
                "source_line_id": line.source_line_id,
                "section": line.section,
                "category_code": line.category_code,
                "description": line.description,
                "unit_raw": line.unit_raw,
                "unit_canonical": line.unit_canonical,
                "unit_status": line.unit_status,
                "qty": line.qty,
                "line_type": line.line_type,
                "spec_requirements": json.dumps([{"kind": r.kind, "raw_text": r.raw_text} for r in line.spec_requirements]),
                "rate": line.rate,
                "amount": line.amount,
            },
        )
    return len(lines)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_boq_lines_storage.py -v`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/boq_lines_store.py tests/integration/test_boq_lines_storage.py
git commit -m "feat(tender): persist atomic BOQ lines with full traceability (P308)"
```

---

### Task 7: Aggregate item-level schema drift

**Files:**
- Modify: `packages/tender/schema_drift.py`
- Create: `tests/unit/test_schema_drift_over_items.py`

**Interfaces:**
- Consumes: `SourceContract`, `detect_schema_drift`, `SchemaDrift` (all already in `schema_drift.py`/`source_contract.py`).
- Produces: `detect_schema_drift_over_items(item_contract: SourceContract, items: list[dict]) -> SchemaDrift`.

- [ ] **Step 1: Write the failing test**

```python
"""FR-TND-10, INT-02: item-level drift inside a page's `items` array must
be detectable too -- today's page-level-only check would silently miss a
per-item field being added/removed/retyped, since `items` itself is just
declared as an opaque 'array' field."""

from __future__ import annotations

from packages.tender.schema_drift import detect_schema_drift_over_items
from packages.tender.source_contract import FieldSpec, SourceContract

ITEM_CONTRACT = SourceContract(
    name="etender.bom_lines_page.item",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("description", "string"),
        FieldSpec("quantity", "number"),
    ),
)


def test_no_drift_when_every_item_matches():
    items = [{"id": 1, "description": "a", "quantity": 1}, {"id": 2, "description": "b", "quantity": 2}]
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, items)
    assert drift.has_drift is False


def test_detects_drift_on_a_single_item_among_many_clean_ones():
    items = [
        {"id": 1, "description": "a", "quantity": 1},
        {"id": 2, "description": "b", "quantity": "2"},  # type changed on this one item only
        {"id": 3, "description": "c", "quantity": 3},
    ]
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, items)
    assert drift.has_drift is True
    assert drift.type_changed_fields == ("quantity",)


def test_aggregates_distinct_drift_kinds_across_different_items_without_duplicates():
    items = [
        {"id": 1, "description": "a", "quantity": 1, "extra": "x"},  # added field
        {"id": 2, "quantity": 2},  # removed field (description)
        {"id": 3, "description": "c", "quantity": 3, "extra": "y"},  # same added field again
    ]
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, items)
    assert drift.added_fields == ("extra",)
    assert drift.removed_fields == ("description",)


def test_empty_items_list_has_no_drift():
    drift = detect_schema_drift_over_items(ITEM_CONTRACT, [])
    assert drift.has_drift is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_schema_drift_over_items.py -v`
Expected: FAIL with `ImportError: cannot import name 'detect_schema_drift_over_items'`

- [ ] **Step 3: Write minimal implementation**

Append to `packages/tender/schema_drift.py`:

```python
def detect_schema_drift_over_items(item_contract: SourceContract, items: list[dict]) -> SchemaDrift:
    """Runs detect_schema_drift once per item and unions the results --
    one drifted item among thousands of clean ones must still be reported,
    not averaged away."""
    added: set[str] = set()
    removed: set[str] = set()
    type_changed: set[str] = set()
    for item in items:
        item_drift = detect_schema_drift(item_contract, item)
        added.update(item_drift.added_fields)
        removed.update(item_drift.removed_fields)
        type_changed.update(item_drift.type_changed_fields)
    return SchemaDrift(
        added_fields=tuple(sorted(added)),
        removed_fields=tuple(sorted(removed)),
        type_changed_fields=tuple(sorted(type_changed)),
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_schema_drift_over_items.py -v`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/schema_drift.py tests/unit/test_schema_drift_over_items.py
git commit -m "feat(tender): detect schema drift inside a page's items array, not just page-level fields (FR-TND-10, INT-02)"
```

---

### Task 8: BOM line item contract

**Files:**
- Modify: `packages/tender/etender_contract.py`
- Create: `tests/unit/test_bom_line_item_contract.py`

**Interfaces:**
- Produces: `BOM_LINE_ITEM_CONTRACT: SourceContract`.

- [ ] **Step 1: Write the failing test**

```python
"""Confirms BOM_LINE_ITEM_CONTRACT matches every item's real key set
observed across all 3 captured BOQ pages of event 355920 -- not a guessed
shape."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_contract import BOM_LINE_ITEM_CONTRACT

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def test_contract_field_names_match_every_real_captured_item_exactly():
    declared = {f.name for f in BOM_LINE_ITEM_CONTRACT.fields}
    for page in (1, 2, 3):
        payload = json.loads((FIXTURES / f"event_355920_bomlines_page{page}.raw.json").read_bytes())
        for item in payload["items"]:
            assert set(item.keys()) == declared
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_bom_line_item_contract.py -v`
Expected: FAIL with `ImportError: cannot import name 'BOM_LINE_ITEM_CONTRACT'`

- [ ] **Step 3: Write minimal implementation**

Append to `packages/tender/etender_contract.py`:

```python
# Per-item shape inside BOM_LINES_PAGE_CONTRACT's `items` array (INT-01,
# INT-02). Verified against every item across all 3 captured pages of
# event 355920's BOQ (see MANIFEST.md) -- categoryCode is constant across
# every item in this fixture (a page/tender-level classification, not a
# per-line distinguishing code), kept anyway because it is the only real
# field mapping to TENDER_INTELLIGENCE_SPEC.md §5.1's `code` concept.
BOM_LINE_ITEM_CONTRACT = SourceContract(
    name="etender.bom_lines_page.item",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("name", "string"),
        FieldSpec("description", "string"),
        FieldSpec("unitOfMeasure", "string"),
        FieldSpec("quantity", "number"),
        FieldSpec("categoryCode", "string"),
    ),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_bom_line_item_contract.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_contract.py tests/unit/test_bom_line_item_contract.py
git commit -m "feat(tender): declare BOM line item contract (INT-01, INT-02)"
```

---

### Task 9: Wire item-level drift into `ingest_bom_lines_page`

**Files:**
- Modify: `packages/tender/etender_connector.py`
- Create: `tests/integration/test_bom_line_item_drift.py`

**Interfaces:**
- Consumes: `detect_schema_drift_over_items` (Task 7), `BOM_LINE_ITEM_CONTRACT` (Task 8).
- Produces: `ingest_bom_lines_page` now also raises `SchemaDriftDetected` (contract_name `"etender.bom_lines_page.item"`) when an item's shape drifts, with raw evidence still saved first -- same guarantee the page-level check already provides.

- [ ] **Step 1: Write the failing test**

```python
"""FR-TND-10, INT-02: an item-level shape change (not just a page-level
one) must still block normalization while keeping the already-saved raw
evidence -- same contract as
test_etender_connector.py::test_schema_drift_blocks_normalization_but_still_saves_raw_evidence,
but for a drift inside `items` rather than at the page's top level."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from packages.tender.etender_connector import SchemaDriftDetected, ingest_bom_lines_page

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load(name: str) -> tuple[bytes, dict]:
    raw_body = (FIXTURES / name).read_bytes()
    return raw_body, json.loads(raw_body)


async def test_real_page_1_has_no_item_level_drift(engine):
    raw_body, payload = _load("event_355920_bomlines_page1.raw.json")
    async with engine.begin() as conn:
        version = await ingest_bom_lines_page(
            conn,
            event_id=355920,
            raw_body=raw_body,
            payload=payload,
            correlation_id="corr-item-drift-1",
        )
    assert version.normalized_fields["event_id"] == 355920


async def test_item_level_type_change_raises_and_still_saves_raw_evidence(engine):
    raw_body, payload = _load("event_355920_bomlines_page1.raw.json")
    drifted_payload = {
        **payload,
        "items": [{**payload["items"][0], "quantity": str(payload["items"][0]["quantity"])}] + payload["items"][1:],
    }

    async with engine.begin() as conn:
        try:
            await ingest_bom_lines_page(
                conn,
                event_id=355920,
                raw_body=raw_body,
                payload=drifted_payload,
                correlation_id="corr-item-drift-2",
            )
            raised = False
        except SchemaDriftDetected as exc:
            raised = True
            assert exc.contract_name == "etender.bom_lines_page.item"

    assert raised is True

    async with engine.begin() as conn:
        snapshot_count = (
            (await conn.execute(text("SELECT count(*) AS n FROM raw_snapshots WHERE correlation_id = 'corr-item-drift-2'")))
            .mappings()
            .one()["n"]
        )
        assert snapshot_count == 1  # raw evidence saved even though normalization was blocked

        drift_events = (
            (await conn.execute(text("SELECT payload FROM outbox WHERE event_type = 'schema_drift_event'"))).mappings().all()
        )
        assert any(e["payload"]["contract"] == "etender.bom_lines_page.item" for e in drift_events)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_bom_line_item_drift.py -v`
Expected: FAIL — the second test does not raise `SchemaDriftDetected` yet (item-level drift is not checked at all today).

- [ ] **Step 3: Write minimal implementation**

Modify `packages/tender/etender_connector.py`:

```python
from .etender_contract import BOM_LINE_ITEM_CONTRACT, BOM_LINES_PAGE_CONTRACT, EVENT_DETAILS_CONTRACT, EVENTS_LIST_PAGE_CONTRACT
from .schema_drift import SchemaDrift, detect_schema_drift, detect_schema_drift_over_items
```

Change `_ingest`'s signature and body to accept an optional item-level contract:

```python
async def _ingest(
    conn: AsyncConnection,
    *,
    contract: SourceContract,
    identity_params: dict[str, Any],
    raw_body: bytes,
    payload: dict[str, Any],
    normalize_fields: Callable[[dict[str, Any]], dict[str, Any]],
    correlation_id: str,
    item_contract: SourceContract | None = None,
    items_extractor: Callable[[dict[str, Any]], list[dict[str, Any]]] | None = None,
) -> TenderVersion:
    identity_key = canonical_identity(contract, identity_params)

    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type=contract.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=contract.name,
        correlation_id=correlation_id,
    )

    drift = detect_schema_drift(contract, payload)
    if not drift.has_drift and item_contract is not None and items_extractor is not None:
        drift = detect_schema_drift_over_items(item_contract, items_extractor(payload))
        drifted_contract_name = item_contract.name
    else:
        drifted_contract_name = contract.name

    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type="tender_source_contract",
            aggregate_id=drifted_contract_name,
            event_type="schema_drift_event",
            payload={
                "contract": drifted_contract_name,
                "identity_key": identity_key,
                "added_fields": list(drift.added_fields),
                "removed_fields": list(drift.removed_fields),
                "type_changed_fields": list(drift.type_changed_fields),
            },
            correlation_id=correlation_id,
        )
        raise SchemaDriftDetected(drift, contract_name=drifted_contract_name, raw_snapshot_id=snapshot_id)

    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)

    return await create_normalized_version(
        conn,
        tender_id=tender_id,
        raw_snapshot_id=snapshot_id,
        parser_version=PARSER_VERSION,
        normalized_fields=normalize_fields(payload),
    )
```

Update `ingest_bom_lines_page` to pass the new params:

```python
    return await _ingest(
        conn,
        contract=BOM_LINES_PAGE_CONTRACT,
        identity_params={"event_id": event_id, "PageNumber": payload["currentPage"]},
        raw_body=raw_body,
        payload=payload,
        normalize_fields=normalize_fields,
        correlation_id=correlation_id,
        item_contract=BOM_LINE_ITEM_CONTRACT,
        items_extractor=lambda p: p["items"],
    )
```

(`ingest_event_details` and `ingest_events_list_page` are unchanged -- they simply don't pass `item_contract`/`items_extractor`, so `_ingest`'s new parameters default to `None` and behave exactly as before for them.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_bom_line_item_drift.py -v`
Expected: PASS (2 passed)

Then re-run the full existing connector suite to confirm nothing regressed:

Run: `python -m pytest tests/integration/test_etender_connector.py tests/integration/test_bom_lines_pagination.py -v`
Expected: all previously-passing tests still PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py tests/integration/test_bom_line_item_drift.py
git commit -m "feat(tender): detect and report item-level schema drift in BOM lines pages (FR-TND-10, INT-02)"
```

---

### Task 10: Wire BOQ line building + storage into the page job — closes P308

**Files:**
- Modify: `packages/tender/bom_lines_job.py`
- Modify: `tests/integration/test_bom_lines_pagination.py`

**Interfaces:**
- Consumes: `build_boq_lines` (Task 5), `store_boq_lines` (Task 6).
- Produces: `process_bom_lines_page`'s returned checkpoint dict gains a `"boq_lines_stored": int` key.

- [ ] **Step 1: Write the failing test**

Add to `tests/integration/test_bom_lines_pagination.py` (extends the existing real-3-page test rather than duplicating its setup):

```python
from sqlalchemy import text as _text  # already imported as `text` above; reuse that import, do not add a second one


async def test_boq_lines_are_stored_for_every_real_page_processed(engine):
    from packages.tender.bom_lines_job import process_bom_lines_page
    from packages.platform.jobs import JobStore

    store = JobStore()
    worker_id = "w1"
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity(correlation_id="corr-boq-lines-1"))
        await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)

    for _ in range(3):
        async with engine.begin() as conn:
            job = await store.get(conn, job_id)
            checkpoint = await process_bom_lines_page(conn, job, _load_page)
            assert checkpoint["boq_lines_stored"] == 100
            await store.checkpoint(conn, job_id, worker_id, checkpoint)

    async with engine.begin() as conn:
        total_lines = (
            (await conn.execute(text("SELECT count(*) AS n FROM boq_lines WHERE event_id = 355920"))).mappings().one()["n"]
        )
        every_line_has_unit_and_qty = (
            (
                await conn.execute(
                    text(
                        "SELECT count(*) AS n FROM boq_lines "
                        "WHERE event_id = 355920 AND (unit_raw IS NULL OR unit_raw = '' OR qty IS NULL)"
                    )
                )
            )
            .mappings()
            .one()["n"]
        )
    # P308 (real-data half): every real line across all 3 pages decomposed,
    # each with a non-null unit + qty.
    assert total_lines == 300
    assert every_line_has_unit_and_qty == 0


async def test_item_level_drift_skips_boq_lines_for_that_page_same_as_page_level_drift(engine):
    from packages.tender.bom_lines_job import process_bom_lines_page
    from packages.platform.jobs import JobStore

    store = JobStore()
    worker_id = "w1"
    async with engine.begin() as conn:
        job_id = await store.enqueue(conn, _identity(correlation_id="corr-boq-lines-drift"))
        await store.claim(conn, worker_id=worker_id, lease_seconds=LEASE_SECONDS)

    async def drifted_fetch_page(event_id: int, page_number: int) -> tuple[bytes, dict]:
        raw_body, payload = await _load_page(event_id, page_number)
        drifted = {
            **payload,
            "items": [{**payload["items"][0], "quantity": str(payload["items"][0]["quantity"])}] + payload["items"][1:],
        }
        return raw_body, drifted

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
        checkpoint = await process_bom_lines_page(conn, job, drifted_fetch_page)
        await store.checkpoint(conn, job_id, worker_id, checkpoint)

    assert checkpoint["boq_status"] is None  # same P305 skip-path as page-level drift
    assert checkpoint["next_page"] == 2  # pagination still advances, one drifted page doesn't stall the job

    async with engine.begin() as conn:
        lines_for_this_page = (
            (await conn.execute(text("SELECT count(*) AS n FROM boq_lines WHERE event_id = 355920 AND page_number = 1")))
            .mappings()
            .one()["n"]
        )
    assert lines_for_this_page == 0  # a page that failed drift-checking stores no guessed lines
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_bom_lines_pagination.py -v`
Expected: FAIL — `checkpoint["boq_lines_stored"]` raises `KeyError` (not returned yet).

- [ ] **Step 3: Write minimal implementation**

Modify `packages/tender/bom_lines_job.py`:

```python
from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .boq_completeness import record_page_fetched
from .boq_line_model import build_boq_lines
from .boq_lines_store import store_boq_lines
from .etender_connector import SchemaDriftDetected, ingest_bom_lines_page
from .raw_snapshot import checksum_of
```

Replace the success path (after the `try/except SchemaDriftDetected` block, once `version` is obtained) so it now also builds and stores lines:

```python
    boq_status = await record_page_fetched(
        conn,
        source="etender",
        event_id=event_id,
        page_number=next_page,
        lines_on_page=payload["itemsInPage"],
        expected_total=payload.get("totalItems"),
        expected_pages=payload.get("totalPages"),
        page_checksum=checksum_of(raw_body),
    )

    lines = build_boq_lines(page_number=next_page, items=payload["items"])
    boq_lines_stored = await store_boq_lines(
        conn,
        source="etender",
        event_id=event_id,
        tender_version_id=version.id,
        raw_snapshot_id=version.raw_snapshot_id,
        lines=lines,
    )

    total_pages = payload.get("totalPages")
    done = total_pages is not None and next_page >= total_pages

    return {
        "next_page": next_page + 1,
        "done": done,
        "tender_version_id": version.id,
        "boq_status": boq_status.status,
        "boq_lines_stored": boq_lines_stored,
    }
```

And add `"boq_lines_stored": 0` to the `SchemaDriftDetected` except-branch's returned dict (a drifted page stores zero lines, explicitly, not an absent key):

```python
        return {
            "next_page": next_page + 1,
            "done": done,
            "tender_version_id": None,
            "boq_status": None,
            "exception_queue_id": exception_record.id,
            "boq_lines_stored": 0,
        }
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_bom_lines_pagination.py -v`
Expected: PASS (all tests in the file, old and new)

Then run the whole non-Docker-independent-of-this-file regression sweep for this task's area:

Run: `python -m pytest tests/unit/test_boq_line_model.py tests/unit/test_schema_drift_over_items.py tests/unit/test_bom_line_item_contract.py tests/integration/test_boq_lines_migration.py tests/integration/test_boq_lines_storage.py tests/integration/test_bom_line_item_drift.py tests/integration/test_bom_lines_pagination.py tests/integration/test_etender_connector.py -v`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/bom_lines_job.py tests/integration/test_bom_lines_pagination.py
git commit -m "feat(tender): store atomic BOQ lines per page, closes P308 (real-data half; see plan's ground-truth note for the constructed-data half)"
```

---

### Task 11: Docs — WORKLOG, README, OPEN-QUESTIONS

**Files:**
- Modify: `packages/tender/README.md`
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

**Interfaces:** none (docs only).

- [ ] **Step 1: Update `packages/tender/README.md`**

Replace:
```markdown
Not implemented yet — Phase 1 (worker-connector) scope, starting task 1.A.
```
with:
```markdown
Phase 1 (raw snapshot, normalized versioning, resumable BOQ pagination, schema drift, exception queue) is done. Phase 2 task 2.A adds atomic BOQ line decomposition (`boq_line_model.py`, `boq_lines_store.py`) — unit canonicalization, preliminaries/provisional-sum/prime-cost typing, hidden spec-requirement extraction (`TENDER_INTELLIGENCE_SPEC.md` §5.1, P308).
```

- [ ] **Step 2: Append a WORKLOG.md entry**

Append to `docs/reports/WORKLOG.md` (do not edit any existing entry — `AGENTS.md` §4 is append-only):

```markdown
## 2026-08-05 — Phase 2, task 2.A (tender): atomic BOQ line depth

**Сделано:**
- `packages/tender/boq_line_model.py` — pure line-model assembly: unit canonicalization (`canonicalize_unit`, real-observed units `ədəd`/`m`/`dəst` mapped, everything else flagged `unmapped` not guessed), line-type classification (`classify_line_type` — preliminaries/provisional_sum/prime_cost, English keywords only, see Open Questions below), hidden spec-requirement extraction (`extract_spec_requirements` — concrete grade B/M-style, rebar class, AZS/ГОСТ/GOST/EN standard references, "or equivalent" RU/AZ/EN), `build_boq_lines` assembling one `BoqLine` per source item.
- `migrations/0007_boq_lines.sql` + `packages/tender/boq_lines_store.py` — atomic `boq_lines` table with full traceability (`tender_version_id`, `raw_snapshot_id`), unique on `(source, event_id, source_line_id)`.
- `packages/tender/schema_drift.py` — `detect_schema_drift_over_items`, closing a real gap: page-level drift detection never validated what was inside the `items` array. `etender_contract.py`'s new `BOM_LINE_ITEM_CONTRACT` + `etender_connector.py`'s `_ingest`/`ingest_bom_lines_page` now check item-shape drift the same way page-shape drift was already checked (FR-TND-10, INT-02).
- `packages/tender/bom_lines_job.py` — `process_bom_lines_page` now builds and stores BOQ lines for every cleanly-ingested page; a page that fails item-level drift stores zero lines (same P305 skip-and-continue precedent as page-level drift), not a guessed partial set.

**P308 closure — honest split (real fixture data has real limits, recorded not hidden):** the real captured BOQ (event 355920, 4135 lines/42 pages, electrical works) proves the "every real line decomposes with unit+qty" half of P308 end-to-end (`tests/integration/test_bom_lines_pagination.py::test_boq_lines_are_stored_for_every_real_page_processed`). It contains **zero** preliminaries/provisional-sum/prime-cost lines and zero hidden spec requirements (no concrete-works vocabulary in an electrical-works BOQ) — that half of P308 is proven only against realistic-but-constructed test data (`tests/unit/test_boq_line_model.py`), not against this real fixture, because this real fixture genuinely doesn't contain any. Not claimed otherwise.

**Вывод полного прогона:**
```
$ python -m pytest tests/ -q
<paste actual count here when run>
$ python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
<paste actual output here when run>
```

**Дальше:** task 2.A closed. Next per `TENDER_INTELLIGENCE_SPEC.md` §5: task 2.B (signal ingestion).

**Блокеры:** нет новых. Non-blocking open question recorded in `docs/decisions/OPEN-QUESTIONS.md` (Azerbaijani/Russian preliminaries/provisional-sum/prime-cost keyword equivalents not implemented, no source document supplies them).
```

(Fill in the actual `pytest`/`ruff`/`mypy`/`check_v1_untouched.py` output before committing — do not paste placeholder text into the real file. Run the commands from Global Constraints and copy their real output, exactly as every prior WORKLOG entry does.)

- [ ] **Step 3: Append an OPEN-QUESTIONS.md entry**

Append to `docs/decisions/OPEN-QUESTIONS.md`:

```markdown
## 2026-08-05 — Task 2.A: preliminaries/provisional-sum/prime-cost keywords are English-only

**Context:** `TENDER_INTELLIGENCE_SPEC.md` §5.1 names `preliminaries`, `provisional sums`, and `prime cost`
as line types to detect, giving only their English terms. The actual source data (eTender, Azerbaijan) is
in Azerbaijani.

**Deviation/assumption:** `classify_line_type` (`packages/tender/boq_line_model.py`) matches English keywords
only. No Azerbaijani or Russian equivalent terms are implemented, because no source document (the spec, the
PRD, the master plan) supplies them, and guessing a translation would be inventing an unsourced fact
(`AGENTS.md` hard ban #2's spirit, even though this isn't a `TBD-nn` financial number specifically).

**Consequence that must not be silently dropped:** a real Azerbaijani-language BOQ line that IS a
preliminaries/provisional-sum/prime-cost line, described only in Azerbaijani, will currently classify as
`normal` — a false negative, not a crash or a guess. `unit_status`/schema-drift-style visibility does not
cover this; it is a silent-until-flagged gap in the classifier's recall, not its precision.

**Owner follow-up needed:** Yes, non-blocking. Confirm the correct Azerbaijani/Russian terms for these three
line types (or confirm English-only is acceptable because BOQ documents on this source are bilingual/English
in practice for these specific line types) before Phase 2.C (forecast engine) or any matching/costing logic
starts relying on `line_type` for anything beyond the English-labeled real-world cases proven so far.
```

- [ ] **Step 4: No automated test for this step** — docs-only; verify by reading the three files back.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/README.md docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs: close out Phase 2 task 2.A (BOQ line depth) — WORKLOG entry, README update, keyword-gap open question"
```

---

## Self-Review

**1. Spec coverage** (`TENDER_INTELLIGENCE_SPEC.md` §5.1):
- Line model `{раздел, code, description, unit, qty, spec_extracted, rate?, amount?}` → `BoqLine` (Task 5): `section`, `category_code`, `description`, `unit_raw`/`unit_canonical`/`unit_status`, `qty`, `spec_requirements`, `rate`, `amount`. Covered.
- Hidden requirements (concrete grade, rebar class, standard, "or equivalent") → `extract_spec_requirements` (Task 4). Covered, with the real-data-vs-constructed-data honesty split documented rather than hidden.
- Preliminaries/provisional sums/prime cost as distinct types → `classify_line_type` (Task 3). Covered, with the English-only limitation recorded as an open question (Task 11), not silently assumed complete.
- Unit canonicalization + nomenclature synonym merging → `canonicalize_unit` (Task 2) covers canonicalization. **Nomenclature synonym merging (e.g. two differently-worded descriptions for the same physical item) is explicitly NOT covered by this plan** — it needs a matching/dedup strategy of its own (likely shared with Phase 2's later matching work) and inventing one here would be scope creep beyond what task 2.A's own acceptance criterion (P308) requires. Flagging this as a real gap rather than silently folding a guessed implementation into this plan: **recommend a follow-up plan once Phase 2.A's line model is in use and there's a real synonym example to design against**, not before.
- P308 acceptance text → Task 10, with the honest real-vs-constructed split repeated in Task 11's WORKLOG entry so it isn't lost.

**2. Placeholder scan:** No `TODO`/`TBD`/"add error handling" phrases in any step. The one deliberate exception — the WORKLOG entry's `<paste actual output here when run>` — is intentionally not fabricated numbers; the step explicitly instructs the implementer to run the real commands and paste real output, matching how every other WORKLOG entry in this repo was actually produced (see e.g. the 1.E entry's real `168 passed, 33 skipped` counts, which cannot be known until this plan's own tests are actually run).

**3. Type consistency:** `BoqLine.qty`/`rate`/`amount` are `Decimal` everywhere they appear (Tasks 5, 6, 10) — no `float` slips in anywhere. `CanonicalUnit`/`SpecRequirement`/`BoqLine` field names are used identically across Tasks 2–6, 10 (`unit_raw`, `unit_canonical`, `unit_status`, `line_type`, `spec_requirements`, `category_code`, `source_line_id`, `page_number`). `store_boq_lines`'s keyword args in Task 6's test and Task 10's wiring match exactly (`source`, `event_id`, `tender_version_id`, `raw_snapshot_id`, `lines`).
