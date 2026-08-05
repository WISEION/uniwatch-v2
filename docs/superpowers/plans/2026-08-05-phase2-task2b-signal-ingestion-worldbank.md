# Phase 2, Task 2.B — Signal ingestion (World Bank donor-pipeline slice) — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the generic signal-ingestion mechanism required by `TENDER_INTELLIGENCE_SPEC.md`
§5.2 (task 2.B) — a source-agnostic `Signal` fact model obeying `INV-15`/`INV-16`/`INV-17` — and prove
it end-to-end against exactly **one** real, live external source: the World Bank Projects API
(`search.worldbank.org`), which is a genuine instance of the "donor pipelines (WB/ADB/EBRD/AIIB)"
signal category named in the spec. `P309` is the acceptance criterion.

**Architecture:** `packages/tender` gets a new, source-agnostic `signal_model.py` (the `Signal`
dataclass — `{value, source_ref, observed_at, ttl_class, confidence}` per `INV-15`, plus a minimal
object binding — `object_customer`/`object_region`/`object_project_type`) and `signals_store.py`
(append-only persistence — signals accumulate, they are never updated in place, matching
`raw_snapshots`' own append-only design and `TENDER_INTELLIGENCE_SPEC.md` §5.3's "накопленные
сигналы"). One concrete connector, `worldbank_contract.py` + `worldbank_connector.py` +
`worldbank_pipeline_job.py`, is built directly from a real live capture and reuses the *existing*
generic mechanisms from task 1.A/1.C unchanged: `source_contract.py`/`schema_drift.py` (extended, see
Task 2) for empirical-contract validation, `raw_snapshot.py` for evidence capture, `exception_queue.py`
for schema-drift handling, `packages/platform/jobs.py` for resumable pagination, and
`packages/platform/egress/*` for the actual live HTTP fetch (unlike task 1.B, egress validation
already exists — this connector does not defer live fetching to a future task).

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async + `asyncpg`, PostgreSQL (via `testcontainers` in
tests), pytest/pytest-asyncio — no new dependencies.

## Global Constraints

- No fabricated data. All example values below (`P505208`, `"Azerbaijan Scaling-Up Renewable Energy
  Project"`, `"250,000,000"`, field-presence counts like `impagency` present in 33/79 records) come
  from a real, live capture against `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ`
  made 2026-08-05 during this task's reconnaissance (79 real Azerbaijan-country World Bank project
  records fetched and inspected field-by-field). Task 1 re-captures and freezes two of those pages as
  fixtures; do not hand-type JSON into the fixture files — save the exact live response bytes.
- Requirement IDs used here trace to: `INV-15`, `INV-16`, `INV-17` (`TENDER_INTELLIGENCE_SPEC.md` §2,
  new — not previously implemented in this repo), `INT-01`, `INT-02`, `FR-TND-10` (empirical contract —
  already implemented, task 1.A/2.A; extended here, see Task 2), `DM-02`, `DM-03` (raw evidence —
  already implemented, reused unchanged), `FR-JOB-01..06` (durable jobs — already implemented, reused
  unchanged), `FR-JOB-08` (exception queue — already implemented, reused unchanged), `INV-10`,
  `NFR-SEC-01..03` (egress validator — already implemented, task 1.C; reused, one new trusted-source
  registration), `P309` (this task's acceptance criterion).
- **`INV-17` (TTL) is a label, not a number.** `ttl_class` on a `Signal` is a category string (e.g.
  `"funding_decision"`, matching `TENDER_INTELLIGENCE_SPEC.md` §2's own worked example "распоряжение о
  финансировании — 12–24 мес"). The actual duration/expiry math for any `ttl_class` is **not** built
  here — exact numbers remain `TBD-TIS-01` (same open status as the PRD's `TBD-01`). Do not invent a
  number and do not compute an expiry timestamp from a guessed duration.
- **`confidence` is a qualitative provenance tier, not a calibrated probability.** It answers "how
  structurally reliable is this class of source" (fixed per connector — e.g. `"official_source"` for a
  first-party donor-institution API), never a forecast percentage. The forecast engine's calibrated
  percentages (`TBD-TIS-02`, illustrative ≈30/60/85% in `TENDER_INTELLIGENCE_SPEC.md` §5.3) are task
  2.C's concern, built on *multiple* signals — this task produces single, unweighted signal facts only.
- **Object binding is minimal, not the object graph.** `TENDER_INTELLIGENCE_SPEC.md` §5.3 assigns "граф
  объектов" to task 2.C. This task adds three plain nullable text columns to `signals`
  (`object_customer`, `object_region`, `object_project_type`) so a signal is never "висит сам по себе"
  (`INV-15`) — it does not create an `objects` table, foreign key, or graph structure. A later task
  (2.C) may need to backfill/reshape this; that is explicitly out of scope here.
- **Scope is the World Bank Projects API only.** `TENDER_INTELLIGENCE_SPEC.md` §5.2 names six signal
  source categories (budgets/investment programs; presidential/cabinet decrees via president.az/
  e-qanun.az; donor pipelines WB/ADB/EBRD/AIIB; TEO/design tenders; annual procurement plans and their
  changes; customer vacancies/appointments). This task closes exactly one instance of one category
  (donor pipelines, World Bank). The other five categories and the other three donor institutions
  (ADB/EBRD/AIIB) are **not started** by this task — same incremental discipline task 1.A used when it
  proved the mechanism against eTender's `event_details` resource before `bom_lines`/`events_list`.
- Migration numbering continues from `0007_boq_lines.sql` → `0008_signals.sql`. `EXPECTED_SCHEMA_VERSION`
  and every test hardcoding the current schema version (`7`) must be bumped to `8` in the same commit
  that adds the migration (task 2.A's own follow-up entry in `docs/reports/WORKLOG.md` records exactly
  this class of mistake — don't repeat it).
- Fixture location: `fixtures/tender-snapshots/worldbank/` (an new source-named subdirectory beside the
  existing `etender/` one — `fixtures/README.md`'s description of `tender-snapshots/` is updated in
  Task 1 to say "per-source subdirectories", not just eTender; the top-level `fixtures/{synthetic,
  tender-snapshots}` structure from `CLAUDE.md`'s repo map is unchanged).

---

## Task 1: Real fixture capture — World Bank Projects API (Azerbaijan)

**Files:**
- Create: `fixtures/tender-snapshots/worldbank/az_donor_pipeline_page_os0.raw.json`
- Create: `fixtures/tender-snapshots/worldbank/az_donor_pipeline_page_os10.raw.json`
- Create: `fixtures/tender-snapshots/worldbank/MANIFEST.md`
- Modify: `fixtures/README.md:4`

**Interfaces:**
- Produces: two real, frozen JSON response bodies used as contract/drift fixtures by every later task.

- [ ] **Step 1: Capture page 1 (offset 0) live**

Run:
```bash
curl -s "https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=10&os=0" \
  -o fixtures/tender-snapshots/worldbank/az_donor_pipeline_page_os0.raw.json
```

Expected shape (verified live 2026-08-05): top-level keys `rows` (number, `10`), `os` (string, `"0"`),
`page` (string, `"1"`), `total` (string, `"79"`), `projects` (object keyed by project id — 10 entries:
`P181649`, `P174379`, `P171250`, `P155110`, `P156377`, `P144700`, `P122812`, `P146125`, `P122944`,
`P122943`), `facets` (empty object).

- [ ] **Step 2: Capture page 2 (offset 10) live**

Run:
```bash
curl -s "https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=10&os=10" \
  -o fixtures/tender-snapshots/worldbank/az_donor_pipeline_page_os10.raw.json
```

Expected shape: same top-level keys, `os`: `"10"`, `page`: `"2"`, `total`: `"79"`, 10 different project
ids (`P125741`, `P107617`, `P120321`, `P122236`, `P118023`, `P115396`, `P100668`, `P110682`, `P110679`,
`P104985`) — genuinely distinct project records from page 1, not a duplicate, for the same reason task
1.B captured distinct real BOM-line pages (a real "resume after failure, don't skip/duplicate" test
needs genuinely different content).

- [ ] **Step 3: Compute checksums and write the manifest**

Run:
```bash
sha256sum fixtures/tender-snapshots/worldbank/az_donor_pipeline_page_os0.raw.json \
          fixtures/tender-snapshots/worldbank/az_donor_pipeline_page_os10.raw.json
```

Write `fixtures/tender-snapshots/worldbank/MANIFEST.md`:

```markdown
# World Bank Projects API frozen fixtures — capture manifest

Real, live captures against `https://search.worldbank.org/api/v2/projects` (INT-01, INT-02, FR-TND-10
— empirical contract, not fabricated data). Captured 2026-08-05, task 2.B
(`TENDER_INTELLIGENCE_SPEC.md` §5.2).

| File | Method | URL | HTTP status | sha256 |
|---|---|---|---|---|
| `az_donor_pipeline_page_os0.raw.json` | GET | `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=10&os=0` | 200 | `<paste sha256sum output>` |
| `az_donor_pipeline_page_os10.raw.json` | GET | `https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ&rows=10&os=10` | 200 | `<paste sha256sum output>` |

Files are the exact raw response bytes, unmodified — layer-1 raw evidence
(`docs/adr/0003-data-authority-and-provenance.md`). Do not hand-edit them; a re-capture creates a new
dated file, never an edit of these.

## What these confirm

- Azerbaijan has 79 total World Bank projects on record; statuses observed across the full set (fetched
  separately during reconnaissance, not itself a frozen fixture): 4 `Active`, 61 `Closed`, 13 `Dropped`,
  1 `Pipeline`. The one `Pipeline`-status record (`P505208`, "Azerbaijan Scaling-Up Renewable Energy
  Project", `totalamt: "250,000,000"`) is the genuine early-signal case this task targets — it has no
  `boardapprovaldate`, no `borrower`, no `impagency` (all three keys entirely absent from that record,
  not merely null) because the project has not yet been approved. This is real API behavior, not a
  gap in this fixture.
- Field presence across all 79 real AZ records is genuinely heterogeneous — e.g. `borrower` appears in
  28/79, `impagency` in 33/79, `boardapprovaldate` in 62/79, `sector2` in 51/79, `closingdate` in 55/79.
  `sector1.Name` and `mjtheme_namecode[].name` are non-empty in most records (71/79, 70/79) but
  genuinely blank strings in some, independent of status. This is why task 2's contract needs an
  `optional` field concept that task 1.A's eTender contracts never needed (eTender's resources had a
  fixed shape every time).
```

- [ ] **Step 4: Update `fixtures/README.md`**

Change line 4 from:
```
- `tender-snapshots/` — frozen real eTender fixtures backing the empirical-contract connector and its schema-drift detector (`FR-TND-10`, `INT-01`, `INT-02`). A fixture change is how `schema_drift_event` gets exercised in tests — fixtures here are deliberately versioned, not just "sample data."
```
to:
```
- `tender-snapshots/` — frozen real fixtures (one subdirectory per source — `etender/`, `worldbank/`, ...) backing empirical-contract connectors and their schema-drift detectors (`FR-TND-10`, `INT-01`, `INT-02`). A fixture change is how `schema_drift_event` gets exercised in tests — fixtures here are deliberately versioned, not just "sample data."
```

- [ ] **Step 5: Commit**

```bash
git add fixtures/tender-snapshots/worldbank/ fixtures/README.md
git commit -m "test(tender): capture real World Bank Projects API fixtures for task 2.B"
```

---

## Task 2: Extend `FieldSpec`/`schema_drift.py` with optional-field support

**Files:**
- Modify: `packages/tender/source_contract.py`
- Modify: `packages/tender/schema_drift.py`
- Test: `tests/unit/test_schema_drift.py`

**Interfaces:**
- Consumes: nothing new.
- Produces: `FieldSpec(name: str, type: str, optional: bool = False)` — `optional=True` fields are not
  reported as `removed_fields` when the actual payload's key is absent. This is additive: every
  existing `FieldSpec(...)` call site (all of `etender_contract.py`) keeps working unchanged because
  `optional` defaults to `False`.

- [ ] **Step 1: Write the failing test**

```python
def test_optional_field_absent_is_not_drift():
    contract = SourceContract(
        name="test.optional",
        identity_query_keys=("id",),
        fields=(
            FieldSpec("id", "number"),
            FieldSpec("nickname", "string", optional=True),
        ),
    )
    drift = detect_schema_drift(contract, {"id": 1})
    assert not drift.has_drift


def test_required_field_absent_is_still_drift():
    contract = SourceContract(
        name="test.required",
        identity_query_keys=("id",),
        fields=(
            FieldSpec("id", "number"),
            FieldSpec("nickname", "string"),
        ),
    )
    drift = detect_schema_drift(contract, {"id": 1})
    assert drift.has_drift
    assert drift.removed_fields == ("nickname",)


def test_optional_field_present_with_wrong_type_is_still_drift():
    contract = SourceContract(
        name="test.optional_type",
        identity_query_keys=("id",),
        fields=(
            FieldSpec("id", "number"),
            FieldSpec("nickname", "string", optional=True),
        ),
    )
    drift = detect_schema_drift(contract, {"id": 1, "nickname": 42})
    assert drift.has_drift
    assert drift.type_changed_fields == ("nickname",)
```

Add these to `tests/unit/test_schema_drift.py`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_schema_drift.py -v`
Expected: `test_optional_field_absent_is_not_drift` and the other two FAIL with `TypeError:
FieldSpec.__init__() got an unexpected keyword argument 'optional'`.

- [ ] **Step 3: Add `optional` to `FieldSpec`**

In `packages/tender/source_contract.py`, change:
```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str  # "string" | "number" | "boolean" | "null" | "array" | "object"
```
to:
```python
@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str  # "string" | "number" | "boolean" | "null" | "array" | "object"
    optional: bool = False  # True: the source is known to sometimes omit this key entirely
    # (not the same as a present key whose value is null — see schema_drift.py's null-value rule).
```

- [ ] **Step 4: Make `detect_schema_drift` skip optional-and-absent fields**

In `packages/tender/schema_drift.py`, change:
```python
def detect_schema_drift(contract: SourceContract, actual_payload: dict) -> SchemaDrift:
    declared = {field.name: field for field in contract.fields}
    declared_keys = set(declared.keys())
    actual_keys = set(actual_payload.keys())

    removed = tuple(sorted(declared_keys - actual_keys))
    added = tuple(sorted(actual_keys - declared_keys))
```
to:
```python
def detect_schema_drift(contract: SourceContract, actual_payload: dict) -> SchemaDrift:
    declared = {field.name: field for field in contract.fields}
    declared_keys = set(declared.keys())
    actual_keys = set(actual_payload.keys())

    missing_keys = declared_keys - actual_keys
    removed = tuple(sorted(key for key in missing_keys if not declared[key].optional))
    added = tuple(sorted(actual_keys - declared_keys))
```
(The rest of the function — the `type_changed` loop over `declared_keys & actual_keys` — is unchanged;
an optional field that *is* present still has its type checked, per Step 1's third test.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_schema_drift.py -v`
Expected: all PASS, including the three new tests and every pre-existing test in the file (optional
defaults to `False`, so `etender_contract.py`'s contracts are unaffected).

- [ ] **Step 6: Commit**

```bash
git add packages/tender/source_contract.py packages/tender/schema_drift.py tests/unit/test_schema_drift.py
git commit -m "feat(tender): add optional-field support to schema-drift contracts"
```

---

## Task 3: Move `SchemaDriftDetected` into `schema_drift.py`

**Rationale:** `SchemaDriftDetected` is a generic control-flow signal (drift + contract name + raw
snapshot id) with no eTender-specific content, but it currently lives in `etender_connector.py`. Task 7
below needs the exact same exception for the World Bank connector; importing an eTender-named module
from a World Bank connector would be a real, avoidable coupling — not a stylistic nit.

**Files:**
- Modify: `packages/tender/schema_drift.py`
- Modify: `packages/tender/etender_connector.py`
- Modify: `packages/tender/bom_lines_job.py:43`
- Modify: `tests/integration/test_bom_line_item_drift.py:14`
- Modify: `tests/integration/test_subresource_status_independence.py:12`
- Modify: `tests/integration/test_etender_connector.py:19`
- Modify: `CLAUDE.md:98`

**Interfaces:**
- Produces: `SchemaDriftDetected` now importable from `packages.tender.schema_drift` (same fields:
  `drift: SchemaDrift`, `contract_name: str`, `raw_snapshot_id: int`; same `__str__`).

- [ ] **Step 1: Add `SchemaDriftDetected` to `schema_drift.py`**

Append to `packages/tender/schema_drift.py`:
```python
@dataclass
class SchemaDriftDetected(Exception):
    """A drift-free response is required to normalize (INT-02). Generic
    across every source connector — carries which contract drifted and a
    pointer to the raw evidence that was already saved before this raised,
    so the caller can route it to the exception queue with a real raw_ref."""

    drift: SchemaDrift
    contract_name: str
    raw_snapshot_id: int

    def __str__(self) -> str:
        return f"schema drift detected: {self.drift}"
```

- [ ] **Step 2: Remove the duplicate from `etender_connector.py` and import it instead**

In `packages/tender/etender_connector.py`, delete the `@dataclass class SchemaDriftDetected(Exception):
...` block (lines 35-42), and change:
```python
from .schema_drift import SchemaDrift, detect_schema_drift, detect_schema_drift_over_items
```
to:
```python
from .schema_drift import SchemaDrift, SchemaDriftDetected, detect_schema_drift, detect_schema_drift_over_items
```
`etender_connector.py` still exposes `SchemaDriftDetected` at module level via this import (Python
re-binds the name), so nothing downstream that imports it *from etender_connector* breaks — but update
the three call sites below anyway, so the generic exception is imported from its real home rather than
relying on that re-export.

- [ ] **Step 3: Update the four import sites**

`packages/tender/bom_lines_job.py:43` — change:
```python
from .etender_connector import SchemaDriftDetected, ingest_bom_lines_page
```
to:
```python
from .etender_connector import ingest_bom_lines_page
from .schema_drift import SchemaDriftDetected
```

`tests/integration/test_bom_line_item_drift.py:14` — change:
```python
from packages.tender.etender_connector import SchemaDriftDetected, ingest_bom_lines_page
```
to:
```python
from packages.tender.etender_connector import ingest_bom_lines_page
from packages.tender.schema_drift import SchemaDriftDetected
```

`tests/integration/test_subresource_status_independence.py:12` — change:
```python
from packages.tender.etender_connector import SchemaDriftDetected, ingest_bom_lines_page, ingest_event_details
```
to:
```python
from packages.tender.etender_connector import ingest_bom_lines_page, ingest_event_details
from packages.tender.schema_drift import SchemaDriftDetected
```

`tests/integration/test_etender_connector.py:19` — in the existing `from .etender_connector import (...)`
or equivalent multi-line import containing `SchemaDriftDetected` on its own line: remove that line from
the `etender_connector` import and add `from packages.tender.schema_drift import SchemaDriftDetected`
alongside it (read the file first — line 19 is inside a parenthesized multi-line import per the earlier
`Read`, so this is a one-line move, not a rewrite of the whole import block).

- [ ] **Step 4: Update `CLAUDE.md`**

`CLAUDE.md:98` — change `a drift raises `SchemaDriftDetected` (`etender_connector.py`)` to `a drift
raises `SchemaDriftDetected` (`schema_drift.py`)`.

- [ ] **Step 5: Run the full test suite to verify nothing broke**

Run: `python -m pytest tests/ -q`
Expected: same pass/skip counts as before this task (this is a pure move, no behavior change).

- [ ] **Step 6: Commit**

```bash
git add packages/tender/schema_drift.py packages/tender/etender_connector.py packages/tender/bom_lines_job.py \
        tests/integration/test_bom_line_item_drift.py tests/integration/test_subresource_status_independence.py \
        tests/integration/test_etender_connector.py CLAUDE.md
git commit -m "refactor(tender): move SchemaDriftDetected to schema_drift.py (source-agnostic)"
```

---

## Task 4: World Bank source contracts

**Files:**
- Create: `packages/tender/worldbank_contract.py`
- Test: `tests/unit/test_worldbank_contract_fixtures.py`

**Interfaces:**
- Consumes: `FieldSpec`, `SourceContract` (Task 2's extended version).
- Produces: `DONOR_PIPELINE_PAGE_CONTRACT`, `DONOR_PIPELINE_PROJECT_CONTRACT` (both `SourceContract`
  instances), for Task 7's connector to import.

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from packages.tender.schema_drift import detect_schema_drift, detect_schema_drift_over_items
from packages.tender.worldbank_contract import DONOR_PIPELINE_PAGE_CONTRACT, DONOR_PIPELINE_PROJECT_CONTRACT

FIXTURES = Path("fixtures/tender-snapshots/worldbank")


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_page_os0_fixture_is_drift_free():
    payload = _load("az_donor_pipeline_page_os0.raw.json")
    assert not detect_schema_drift(DONOR_PIPELINE_PAGE_CONTRACT, payload).has_drift


def test_page_os10_fixture_is_drift_free():
    payload = _load("az_donor_pipeline_page_os10.raw.json")
    assert not detect_schema_drift(DONOR_PIPELINE_PAGE_CONTRACT, payload).has_drift


def test_every_project_item_in_both_pages_is_drift_free():
    for name in ("az_donor_pipeline_page_os0.raw.json", "az_donor_pipeline_page_os10.raw.json"):
        payload = _load(name)
        projects = list(payload["projects"].values())
        drift = detect_schema_drift_over_items(DONOR_PIPELINE_PROJECT_CONTRACT, projects)
        assert not drift.has_drift, f"{name}: {drift}"
```

Save as `tests/unit/test_worldbank_contract_fixtures.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_worldbank_contract_fixtures.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.worldbank_contract'`.

- [ ] **Step 3: Write the contracts**

```python
"""Concrete World Bank Projects API source contracts (INT-01). Built
directly from a real, live capture against
https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact=AZ
(see fixtures/tender-snapshots/worldbank/MANIFEST.md) — not from official
API documentation, which does not enumerate every field this endpoint
actually returns.

Unlike eTender's fixed-shape resources (etender_contract.py), this API's
project records genuinely vary in which optional fields are present
depending on project status (a Pipeline-stage project has no
`boardapprovaldate`/`borrower`/`impagency` because those facts don't exist
yet, not because of a parsing gap) — hence FieldSpec(..., optional=True)
on those fields."""

from __future__ import annotations

from .source_contract import FieldSpec, SourceContract

DONOR_PIPELINE_PAGE_CONTRACT = SourceContract(
    name="worldbank.donor_pipeline_page",
    identity_query_keys=("countrycode_exact", "os"),
    fields=(
        FieldSpec("rows", "number"),
        FieldSpec("os", "string"),
        FieldSpec("page", "string"),
        FieldSpec("total", "string"),
        FieldSpec("projects", "object"),
        FieldSpec("facets", "object"),
    ),
)

# Per-item shape inside DONOR_PIPELINE_PAGE_CONTRACT's `projects` object
# values (INT-01, INT-02). Required fields were present in all 79 real AZ
# records captured during this task's reconnaissance (2026-08-05); optional
# fields varied — see MANIFEST.md for exact presence counts.
DONOR_PIPELINE_PROJECT_CONTRACT = SourceContract(
    name="worldbank.donor_pipeline_page.project",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "string"),
        FieldSpec("project_name", "string"),
        FieldSpec("status", "string"),
        FieldSpec("projectstatusdisplay", "string"),
        FieldSpec("totalamt", "string"),
        FieldSpec("countryname", "array"),
        FieldSpec("countrycode", "array"),
        FieldSpec("regionname", "string"),
        FieldSpec("source", "array"),
        FieldSpec("mjthemecode", "string"),
        FieldSpec("mjtheme_namecode", "array"),
        FieldSpec("sector1", "object"),
        FieldSpec("url", "string"),
        FieldSpec("teamleadname", "string"),
        FieldSpec("lendinginstr", "string"),
        FieldSpec("borrower", "string", optional=True),
        FieldSpec("impagency", "string", optional=True),
        FieldSpec("boardapprovaldate", "string", optional=True),
        FieldSpec("closingdate", "string", optional=True),
        FieldSpec("approvalfy", "string", optional=True),
        FieldSpec("p2a_updated_date", "string", optional=True),
        FieldSpec("sector2", "object", optional=True),
        FieldSpec("grantamt", "string", optional=True),
    ),
)
```

Save as `packages/tender/worldbank_contract.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_worldbank_contract_fixtures.py -v`
Expected: all 3 PASS. If `test_every_project_item_in_both_pages_is_drift_free` fails, read the assertion
error's `drift` repr — it names the exact field; either it needs `optional=True` (if genuinely absent in
some records per the MANIFEST) or the live capture differs from this plan's account (the World Bank API
is live and could add a field between this plan being written and Task 1 being executed) — in the latter
case, fix the contract to match reality, do not weaken the test.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/worldbank_contract.py tests/unit/test_worldbank_contract_fixtures.py
git commit -m "feat(tender): World Bank Projects API donor-pipeline source contract"
```

---

## Task 5: `signals` migration + `signals_store.py`

**Files:**
- Create: `migrations/0008_signals.sql`
- Create: `packages/tender/signals_store.py`
- Modify: `packages/platform/settings.py` (`EXPECTED_SCHEMA_VERSION` default `7` → `8`)
- Modify: `apps/api/routers/health.py` if it hardcodes a version (read the file first; task 2.A's
  follow-up entry bumped `packages/platform/settings.py`'s env-var default — check whether
  `health.py` itself has a literal too before assuming it doesn't)
- Test: `tests/integration/test_migrations_runner.py` (bump hardcoded `7`s to `8`, same pattern as task
  2.A's "Follow-up" WORKLOG entry: `versions == {1, ..., 7}` → `{1, ..., 8}`, `current_version() == 7`
  → `== 8`, applied-set check, `expected_version=7`/`version == 7` in the startup-check test)
- Test: `tests/integration/test_health.py` (bump `expected_schema_version=7` and `body["schema_version"]
  == 7` to `8`)
- Test: `tests/integration/test_signals_store.py`

**Interfaces:**
- Produces: table `signals(id, signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
  confidence, object_customer, object_region, object_project_type, correlation_id, created_at)`;
  `async def store_signal(conn: AsyncConnection, signal: Signal) -> int` (Task 6 defines `Signal`,
  imported here); `async def list_signals(conn: AsyncConnection, *, signal_type: str) -> list[dict]`
  (test helper, also usable by a future 2.C).

- [ ] **Step 1: Write the migration**

```sql
-- Signal facts (INV-15, INV-16, INV-17, TENDER_INTELLIGENCE_SPEC.md §5.2, P309):
-- append-only atoms, never updated in place -- a re-observation of the same
-- underlying real-world fact is a new row, matching raw_snapshots' own
-- append-only design. object_customer/object_region/object_project_type are
-- a minimal binding (INV-15 "not floating unattached"), not the full object
-- graph (that is task 2.C).

CREATE TABLE signals (
    id BIGSERIAL PRIMARY KEY,
    signal_type TEXT NOT NULL,
    source TEXT NOT NULL,
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    value JSONB NOT NULL,
    observed_at TIMESTAMPTZ NOT NULL,
    -- INV-17: a TTL *class* label (e.g. 'funding_decision'), never a
    -- resolved duration or expiry -- exact numbers are TBD-TIS-01.
    ttl_class TEXT NOT NULL,
    -- INV-15: a qualitative provenance tier (e.g. 'official_source'),
    -- fixed per connector -- never a calibrated forecast probability
    -- (that is TBD-TIS-02 / task 2.C, built from multiple signals).
    confidence TEXT NOT NULL,
    object_customer TEXT,
    object_region TEXT,
    object_project_type TEXT,
    correlation_id TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX signals_type_observed_idx ON signals (signal_type, observed_at);
CREATE INDEX signals_object_idx ON signals (object_customer, object_region, object_project_type);
```

Save as `migrations/0008_signals.sql`.

- [ ] **Step 2: Bump the schema-version constant and the four stale test assertions**

Read `packages/platform/settings.py` and change `EXPECTED_SCHEMA_VERSION` default from `7` to `8`.

Read `tests/integration/test_migrations_runner.py` and `tests/integration/test_health.py` in full,
locate every literal `7` that refers to the schema version (not an unrelated `7`), and bump each to `8`
— mirror exactly the four-assertion + one-fixture pattern from task 2.A's "Follow-up" WORKLOG entry
(`docs/reports/WORKLOG.md`, entry "2026-08-05 — Follow-up: fix stale hardcoded schema version (6 -> 7)
after task 2.A's migration").

- [ ] **Step 3: Run migration tests to verify they pass against the new migration**

Run: `python -m pytest tests/integration/test_migrations_runner.py tests/integration/test_health.py -v`
Expected: all PASS (requires Docker running — testcontainers Postgres).

- [ ] **Step 4: Write the failing test for `signals_store.py`**

```python
import pytest

from packages.tender.raw_snapshot import save_raw_snapshot
from packages.tender.signal_model import Signal
from packages.tender.signals_store import list_signals, store_signal


@pytest.mark.asyncio
async def test_store_and_list_signal_roundtrip(engine):
    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="worldbank_projects_api",
            resource_type="worldbank.donor_pipeline_page",
            identity_key="worldbank.donor_pipeline_page|countrycode_exact=AZ&os=0",
            raw_body=b'{"total":"79"}',
            contract_version="worldbank.donor_pipeline_page",
            correlation_id="test-corr-1",
        )
        signal = Signal(
            signal_type="donor_pipeline_project",
            source="worldbank_projects_api",
            raw_snapshot_id=snapshot_id,
            value={"project_id": "P505208", "project_name": "Azerbaijan Scaling-Up Renewable Energy Project"},
            observed_at="2026-08-05T00:00:00+00:00",
            ttl_class="funding_decision",
            confidence="official_source",
            object_customer=None,
            object_region="Republic of Azerbaijan",
            object_project_type="2",
            correlation_id="test-corr-1",
        )
        signal_id = await store_signal(conn, signal)
        assert signal_id is not None

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        assert len(rows) == 1
        assert rows[0]["value"]["project_id"] == "P505208"
        assert rows[0]["object_customer"] is None
        assert rows[0]["object_region"] == "Republic of Azerbaijan"
```

Save as `tests/integration/test_signals_store.py`.

- [ ] **Step 5: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_signals_store.py -v`
Expected: FAIL with `ModuleNotFoundError` (neither `signal_model.py` nor `signals_store.py` exist yet —
Task 6 creates `signal_model.py`; write a minimal stub `Signal` dataclass now if you want this test
runnable before Task 6, or defer running it until after Task 6 — either order is fine, they're
independent files).

- [ ] **Step 6: Write `signals_store.py`**

```python
"""Append-only signal-fact storage (INV-15, INV-16, INV-17). A signal is
never UPDATEd -- a re-observation is always a new INSERT, same discipline
as raw_snapshot.py, because a signal IS an observation at a point in time,
not a mutable current-state row."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .signal_model import Signal


async def store_signal(conn: AsyncConnection, signal: Signal) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO signals
                    (signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
                     confidence, object_customer, object_region, object_project_type, correlation_id)
                VALUES (:signal_type, :source, :raw_snapshot_id, CAST(:value AS jsonb), :observed_at,
                        :ttl_class, :confidence, :object_customer, :object_region, :object_project_type,
                        :correlation_id)
                RETURNING id
                """
            ),
            {
                "signal_type": signal.signal_type,
                "source": signal.source,
                "raw_snapshot_id": signal.raw_snapshot_id,
                "value": json.dumps(signal.value),
                "observed_at": signal.observed_at,
                "ttl_class": signal.ttl_class,
                "confidence": signal.confidence,
                "object_customer": signal.object_customer,
                "object_region": signal.object_region,
                "object_project_type": signal.object_project_type,
                "correlation_id": signal.correlation_id,
            },
        )
    ).scalar_one()


async def list_signals(conn: AsyncConnection, *, signal_type: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
                           confidence, object_customer, object_region, object_project_type, correlation_id
                    FROM signals WHERE signal_type = :signal_type ORDER BY id
                    """
                ),
                {"signal_type": signal_type},
            )
        )
        .mappings()
        .all()
    )
    result = []
    for row in rows:
        row_dict = dict(row)
        if isinstance(row_dict["value"], str):
            row_dict["value"] = json.loads(row_dict["value"])
        result.append(row_dict)
    return result
```

Save as `packages/tender/signals_store.py`.

- [ ] **Step 7: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_signals_store.py -v`
Expected: PASS (after Task 6's `signal_model.py` exists too).

- [ ] **Step 8: Commit**

```bash
git add migrations/0008_signals.sql packages/tender/signals_store.py packages/platform/settings.py \
        tests/integration/test_migrations_runner.py tests/integration/test_health.py tests/integration/test_signals_store.py
git commit -m "feat(tender): add signals table and append-only signals_store"
```

---

## Task 6: `signal_model.py` — the `Signal` dataclass and donor-pipeline builder

**Files:**
- Create: `packages/tender/signal_model.py`
- Test: `tests/unit/test_signal_model.py`

**Interfaces:**
- Consumes: nothing new (pure dataclass + pure function, no DB, no network — same "pure model
  assembly" shape as task 2.A's `boq_line_model.py`).
- Produces: `Signal` dataclass (fields: `signal_type: str`, `source: str`, `raw_snapshot_id: int`,
  `value: dict[str, Any]`, `observed_at: str`, `ttl_class: str`, `confidence: str`,
  `object_customer: str | None`, `object_region: str | None`, `object_project_type: str | None`,
  `correlation_id: str`) and `build_donor_pipeline_signal(project: dict, *, raw_snapshot_id: int,
  observed_at: str, correlation_id: str) -> Signal`, both consumed by Task 5's tests (already written
  above) and Task 7's connector.

- [ ] **Step 1: Write the failing test**

```python
from packages.tender.signal_model import build_donor_pipeline_signal


def test_pipeline_stage_project_with_no_approval_yet():
    # Real record, captured 2026-08-05 (fixtures/tender-snapshots/worldbank/MANIFEST.md) --
    # a genuine Pipeline-status project with borrower/impagency/boardapprovaldate all absent.
    project = {
        "id": "P505208",
        "project_name": "Azerbaijan Scaling-Up Renewable Energy Project",
        "status": "Pipeline",
        "projectstatusdisplay": "Pipeline",
        "totalamt": "250,000,000",
        "countryname": ["Republic of Azerbaijan"],
        "countrycode": ["AZ"],
        "regionname": "Europe and Central Asia",
        "source": ["IBRD"],
        "mjthemecode": "2",
        "mjtheme_namecode": [{"name": "", "code": "2"}],
        "sector1": {"Name": "", "Percent": 0},
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P505208",
        "teamleadname": "Roger Coma Cunill,Florian Kitt",
        "lendinginstr": "Investment Project Financing",
    }
    signal = build_donor_pipeline_signal(
        project, raw_snapshot_id=42, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-1"
    )
    assert signal.signal_type == "donor_pipeline_project"
    assert signal.source == "worldbank_projects_api"
    assert signal.raw_snapshot_id == 42
    assert signal.value["project_id"] == "P505208"
    assert signal.value["total_amount_usd_text"] == "250,000,000"
    assert signal.value["board_approval_date"] is None
    assert signal.observed_at == "2026-08-05T12:00:00+00:00"
    assert signal.ttl_class == "funding_decision"
    assert signal.confidence == "official_source"
    # honest absence -- neither field exists on this real record, not fabricated.
    assert signal.object_customer is None
    assert signal.object_region == "Republic of Azerbaijan"
    # mjtheme_namecode[0]["name"] is blank on this real record -- falls back to the code.
    assert signal.object_project_type == "2"


def test_active_project_with_named_theme_and_agency():
    # Real record, captured 2026-08-05 -- project_name/impagency/theme name all populated.
    project = {
        "id": "P174379",
        "project_name": "Regional Connectivity and Development Project",
        "status": "Active",
        "projectstatusdisplay": "Active",
        "totalamt": "65,000,000",
        "countryname": ["Republic of Azerbaijan"],
        "countrycode": ["AZ"],
        "regionname": "Europe and Central Asia",
        "source": ["IBRD"],
        "mjthemecode": "5",
        "mjtheme_namecode": [{"name": "Public Administration", "code": "5"}],
        "sector1": {"Name": "Rural and Inter-Urban Roads", "Percent": 100},
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P174379",
        "teamleadname": "Some Team Lead",
        "lendinginstr": "Investment Project Financing",
        "borrower": "Ministry of Finance",
        "impagency": "State Roads Agency",
        "boardapprovaldate": "2021-05-01T00:00:00Z",
    }
    signal = build_donor_pipeline_signal(
        project, raw_snapshot_id=43, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-2"
    )
    assert signal.object_customer == "State Roads Agency"  # impagency preferred over borrower
    assert signal.object_project_type == "Public Administration"  # named theme preferred over code
    assert signal.value["board_approval_date"] == "2021-05-01T00:00:00Z"
```

Save as `tests/unit/test_signal_model.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_signal_model.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.signal_model'`.

- [ ] **Step 3: Write `signal_model.py`**

```python
"""Signal fact model (INV-15, INV-16, INV-17): pure assembly, no DB, no
network -- mirrors boq_line_model.py's "pure model assembly" shape from
task 2.A. `build_donor_pipeline_signal` is the one concrete builder this
task needs; a future signal source gets its own builder function, not a
change to this one (each source's fields differ too much for one generic
mapper to stay honest)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class Signal:
    signal_type: str
    source: str
    raw_snapshot_id: int
    value: dict[str, Any]
    # INV-15: when this fact was actually observed (the raw snapshot's own
    # fetch time) -- not the source's self-reported update timestamp,
    # which is only present on some records (p2a_updated_date, 24/79 in
    # the real capture) and would make observed_at non-deterministic
    # depending on which records happen to carry it.
    observed_at: str
    ttl_class: str
    confidence: str
    object_customer: str | None
    object_region: str | None
    object_project_type: str | None
    correlation_id: str


def build_donor_pipeline_signal(
    project: dict[str, Any],
    *,
    raw_snapshot_id: int,
    observed_at: str,
    correlation_id: str,
) -> Signal:
    theme_name = None
    theme_namecode = project.get("mjtheme_namecode") or []
    if theme_namecode and theme_namecode[0].get("name"):
        theme_name = theme_namecode[0]["name"]

    return Signal(
        signal_type="donor_pipeline_project",
        source="worldbank_projects_api",
        raw_snapshot_id=raw_snapshot_id,
        value={
            "project_id": project["id"],
            "project_name": project["project_name"],
            "status": project["status"],
            # Kept as the source's own formatted string ("250,000,000") --
            # parsing to a numeric type is not needed by anything in this
            # task and is not invented speculatively (YAGNI).
            "total_amount_usd_text": project["totalamt"],
            "board_approval_date": project.get("boardapprovaldate"),
            "closing_date": project.get("closingdate"),
            "lending_instrument": project["lendinginstr"],
            "url": project["url"],
        },
        observed_at=observed_at,
        # INV-17: label only -- a donor-financed pipeline entry is the same
        # TTL *class* as TENDER_INTELLIGENCE_SPEC.md §2's own worked
        # example "распоряжение о финансировании" (funding decision).
        # Exact duration remains TBD-TIS-01.
        ttl_class="funding_decision",
        # INV-15: World Bank publishing its own project pipeline is a
        # first-party official source -- the highest structural-reliability
        # tier this task defines. Not a calibrated probability (TBD-TIS-02).
        confidence="official_source",
        # impagency (implementing agency) is preferred over borrower when
        # both are present -- it is the entity that will actually run
        # procurement, closer to a real tender's buyer than the sovereign
        # borrower. Both are honestly None for a Pipeline-stage project
        # that has neither key at all (see P505208 in the test above).
        object_customer=project.get("impagency") or project.get("borrower"),
        # This source gives country-level geography only -- no
        # sub-national region field exists on this API's project records.
        object_region=project["countryname"][0] if project.get("countryname") else None,
        object_project_type=theme_name or project["mjthemecode"],
        correlation_id=correlation_id,
    )
```

Save as `packages/tender/signal_model.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_signal_model.py -v`
Expected: both PASS.

- [ ] **Step 5: Re-run Task 5's `test_signals_store.py` now that `signal_model.py` exists**

Run: `python -m pytest tests/integration/test_signals_store.py -v`
Expected: PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/signal_model.py tests/unit/test_signal_model.py
git commit -m "feat(tender): Signal fact model and donor-pipeline signal builder"
```

---

## Task 7: `worldbank_connector.py` — raw → drift → signals

**Files:**
- Create: `packages/tender/worldbank_connector.py`
- Test: `tests/integration/test_worldbank_connector.py`

**Interfaces:**
- Consumes: `DONOR_PIPELINE_PAGE_CONTRACT`, `DONOR_PIPELINE_PROJECT_CONTRACT` (Task 4);
  `save_raw_snapshot` (existing, unchanged); `detect_schema_drift`, `detect_schema_drift_over_items`,
  `SchemaDriftDetected` (Task 2/3); `build_donor_pipeline_signal` (Task 6); `store_signal` (Task 5);
  `packages.platform.outbox.enqueue` (existing, unchanged).
- Produces: `async def ingest_donor_pipeline_page(conn, *, raw_body: bytes, payload: dict, os_: int,
  correlation_id: str, observed_at: str) -> list[int]` — returns the list of stored signal ids,
  raises `SchemaDriftDetected` on drift (evidence already saved before the raise, same contract as
  `etender_connector.py`'s `_ingest`).

- [ ] **Step 1: Write the failing test (happy path, real fixture)**

```python
import json
from pathlib import Path

import pytest

from packages.tender.signals_store import list_signals
from packages.tender.worldbank_connector import ingest_donor_pipeline_page

FIXTURES = Path("fixtures/tender-snapshots/worldbank")


@pytest.mark.asyncio
async def test_ingest_real_page_os0_stores_ten_signals(engine):
    raw_body = (FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_donor_pipeline_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            os_=0,
            correlation_id="corr-worldbank-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        assert len(signal_ids) == len(payload["projects"])

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        stored_project_ids = {row["value"]["project_id"] for row in rows}
        assert stored_project_ids == set(payload["projects"].keys())
```

Save as `tests/integration/test_worldbank_connector.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_worldbank_connector.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.worldbank_connector'`.

- [ ] **Step 3: Write `worldbank_connector.py`**

```python
"""World Bank Projects API donor-pipeline ingestion (INT-01, INT-02,
FR-TND-10, TENDER_INTELLIGENCE_SPEC.md §5.2). Raw evidence is captured
unconditionally, before the drift check -- same discipline as
etender_connector.py's `_ingest`. Unlike that connector, a successful
ingest here produces *N* signal rows (one per project in the page), not
one normalized version, because a signal is an independent fact per
project, not a single versioned entity."""

from __future__ import annotations

from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox

from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDriftDetected, detect_schema_drift, detect_schema_drift_over_items
from .signal_model import build_donor_pipeline_signal
from .signals_store import store_signal
from .source_contract import canonical_identity
from .worldbank_contract import DONOR_PIPELINE_PAGE_CONTRACT, DONOR_PIPELINE_PROJECT_CONTRACT


async def ingest_donor_pipeline_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    os_: int,
    correlation_id: str,
    observed_at: str,
) -> list[int]:
    identity_key = canonical_identity(DONOR_PIPELINE_PAGE_CONTRACT, {"countrycode_exact": "AZ", "os": str(os_)})

    snapshot_id = await save_raw_snapshot(
        conn,
        source="worldbank_projects_api",
        resource_type=DONOR_PIPELINE_PAGE_CONTRACT.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=DONOR_PIPELINE_PAGE_CONTRACT.name,
        correlation_id=correlation_id,
    )

    projects = list(payload["projects"].values())
    drift = detect_schema_drift(DONOR_PIPELINE_PAGE_CONTRACT, payload)
    drifted_contract_name = DONOR_PIPELINE_PAGE_CONTRACT.name
    if not drift.has_drift:
        drift = detect_schema_drift_over_items(DONOR_PIPELINE_PROJECT_CONTRACT, projects)
        drifted_contract_name = DONOR_PIPELINE_PROJECT_CONTRACT.name

    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type="signal_source_contract",
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

    signal_ids = []
    for project in projects:
        signal = build_donor_pipeline_signal(
            project, raw_snapshot_id=snapshot_id, observed_at=observed_at, correlation_id=correlation_id
        )
        signal_ids.append(await store_signal(conn, signal))
    return signal_ids
```

Save as `packages/tender/worldbank_connector.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_worldbank_connector.py -v`
Expected: PASS.

- [ ] **Step 5: Write and run the drift-path test**

Add to `tests/integration/test_worldbank_connector.py`:
```python
@pytest.mark.asyncio
async def test_page_level_drift_saves_evidence_and_raises(engine):
    raw_body = (FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes()
    payload = json.loads(raw_body)
    payload["unexpected_new_field"] = "drift"  # a field the frozen contract never declared
    async with engine.begin() as conn:
        with pytest.raises(Exception) as exc_info:
            await ingest_donor_pipeline_page(
                conn,
                raw_body=raw_body,
                payload=payload,
                os_=0,
                correlation_id="corr-worldbank-drift",
                observed_at="2026-08-05T12:00:00+00:00",
            )
        from packages.tender.schema_drift import SchemaDriftDetected

        assert isinstance(exc_info.value, SchemaDriftDetected)
        assert "unexpected_new_field" in exc_info.value.drift.added_fields

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        assert rows == []  # drift blocked signal storage, but evidence below was still saved

        from packages.tender.raw_snapshot import get_raw_snapshot

        snapshot = await get_raw_snapshot(conn, exc_info.value.raw_snapshot_id)
        assert snapshot.body["unexpected_new_field"] == "drift"
```

Run: `python -m pytest tests/integration/test_worldbank_connector.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/worldbank_connector.py tests/integration/test_worldbank_connector.py
git commit -m "feat(tender): World Bank donor-pipeline connector (raw to drift to signals)"
```

---

## Task 8: Resumable pagination job (`worldbank_pipeline_job.py`)

**Files:**
- Create: `packages/tender/worldbank_pipeline_job.py`
- Test: `tests/integration/test_worldbank_pipeline_job.py`

**Interfaces:**
- Consumes: `ingest_donor_pipeline_page`, `SchemaDriftDetected` (Task 7); `enqueue_exception`
  (existing, unchanged); `packages.platform.jobs.Job` (existing, unchanged).
- Produces: `JOB_TYPE = "worldbank_donor_pipeline_page_fetch"`; `FetchPage = Callable[[str, int, int],
  Awaitable[tuple[bytes, dict]]]`; `async def process_worldbank_pipeline_page(conn, job: Job,
  fetch_page: FetchPage, *, observed_at: str) -> dict[str, Any]` — mirrors
  `bom_lines_job.py::process_bom_lines_page`'s exact resumability contract (checkpoint only advances
  after a durable commit; a new job identity gets `checkpoint = {}`).

- [ ] **Step 1: Write the failing test (resume-after-failure, real distinct pages)**

```python
import json
from pathlib import Path

import pytest

from packages.platform.jobs import Job
from packages.tender.worldbank_pipeline_job import process_worldbank_pipeline_page

FIXTURES = Path("fixtures/tender-snapshots/worldbank")


def _make_job(checkpoint: dict) -> Job:
    return Job(
        id=1,
        job_type="worldbank_donor_pipeline_page_fetch",
        params={"countrycode_exact": "AZ", "rows": 10},
        source="worldbank_projects_api",
        range_start=None,
        range_end=None,
        contract_version="worldbank.donor_pipeline_page",
        correlation_id="corr-wb-job-1",
        status="running",
        lease_owner="test-worker",
        attempt=1,
        max_attempts=5,
        checkpoint=checkpoint,
        last_error=None,
    )


@pytest.mark.asyncio
async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    real_page_os0 = json.loads((FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes())
    real_page_os10 = json.loads((FIXTURES / "az_donor_pipeline_page_os10.raw.json").read_bytes())
    attempts = []

    async def fetch_page(countrycode, rows, os_):
        attempts.append(os_)
        if os_ == 0 and attempts.count(0) == 1:
            raise ConnectionError("simulated transient failure on first page")
        raw = (FIXTURES / f"az_donor_pipeline_page_os{os_}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        with pytest.raises(ConnectionError):
            await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert attempts == [0]

        # Retry: same job identity, checkpoint never advanced past the failure.
        job = _make_job(checkpoint={})
        result = await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_os"] == 10
        assert not result["done"]  # total=79, next_os=10 < 79
        assert len(result["signal_ids"]) == len(real_page_os0["projects"])

        # Next page.
        job = _make_job(checkpoint={"next_os": 10})
        result = await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_os"] == 20
        assert len(result["signal_ids"]) == len(real_page_os10["projects"])

        assert attempts == [0, 0, 10]  # first page fetched twice (failed, then succeeded), never skipped to os=10 early
```

Save as `tests/integration/test_worldbank_pipeline_job.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_worldbank_pipeline_job.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.worldbank_pipeline_job'`.

- [ ] **Step 3: Write `worldbank_pipeline_job.py`**

```python
"""Resumable World Bank donor-pipeline pagination (INV-03, FR-JOB-04,
FR-JOB-05, FR-JOB-06). Mirrors bom_lines_job.py's exact shape:
`process_worldbank_pipeline_page` processes exactly one page, resuming
from `job.checkpoint["next_os"]` (0 if never started).

`fetch_page` is an injected dependency, same reason as bom_lines_job.py's
own injection: tests can run against real captured fixtures without a
live network call. Unlike bom_lines_job.py (written in task 1.B, before
1.C's egress validator existed), a real implementation of `fetch_page`
using the egress validator is wired at the apps/worker layer, not deferred
-- see fetch_donor_pipeline_page_live in worldbank_connector.py."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .schema_drift import SchemaDriftDetected
from .worldbank_connector import ingest_donor_pipeline_page

JOB_TYPE = "worldbank_donor_pipeline_page_fetch"

FetchPage = Callable[[str, int, int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_worldbank_pipeline_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    countrycode_exact = job.params["countrycode_exact"]
    rows = job.params["rows"]
    next_os = job.checkpoint.get("next_os", 0)

    raw_body, payload = await fetch_page(countrycode_exact, rows, next_os)

    try:
        signal_ids = await ingest_donor_pipeline_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            os_=next_os,
            correlation_id=job.correlation_id,
            observed_at=observed_at,
        )
    except SchemaDriftDetected as drift_exc:
        exception_record = await enqueue_exception(
            conn,
            source="worldbank_projects_api",
            exception_type="schema_drift",
            category="needs_human",
            reason=str(drift_exc),
            correlation_id=job.correlation_id,
            raw_ref=drift_exc.raw_snapshot_id,
            contract_name=drift_exc.contract_name,
        )
        total = int(payload["total"])
        return {
            "next_os": next_os + rows,
            "done": next_os + rows >= total,
            "signal_ids": [],
            "exception_queue_id": exception_record.id,
        }

    total = int(payload["total"])
    return {
        "next_os": next_os + rows,
        "done": next_os + rows >= total,
        "signal_ids": signal_ids,
    }
```

Save as `packages/tender/worldbank_pipeline_job.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_worldbank_pipeline_job.py -v`
Expected: PASS.

- [ ] **Step 5: Write and run the schema-drift-does-not-stall-the-job test (P305 precedent)**

Add to `tests/integration/test_worldbank_pipeline_job.py`:
```python
@pytest.mark.asyncio
async def test_schema_drift_on_one_page_does_not_stall_pagination(engine):
    real_page_os0 = json.loads((FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes())
    real_page_os0["unexpected_new_field"] = "drift"

    async def fetch_page(countrycode, rows, os_):
        if os_ == 0:
            return json.dumps(real_page_os0).encode(), real_page_os0
        raw = (FIXTURES / f"az_donor_pipeline_page_os{os_}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        result = await process_worldbank_pipeline_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_os"] == 10  # advanced past the drifted page, did not stall
        assert result["signal_ids"] == []
        assert result["exception_queue_id"] is not None
```

Run: `python -m pytest tests/integration/test_worldbank_pipeline_job.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/worldbank_pipeline_job.py tests/integration/test_worldbank_pipeline_job.py
git commit -m "feat(tender): resumable pagination job for World Bank donor-pipeline signals"
```

---

## Task 9: Live egress-validated fetch + real-network proof test

**Files:**
- Modify: `packages/tender/worldbank_connector.py`
- Test: `tests/security/test_worldbank_live_fetch.py`

**Interfaces:**
- Produces: `async def fetch_donor_pipeline_page_live(conn, validator: EgressValidator, *,
  countrycode_exact: str, rows: int, os_: int) -> tuple[bytes, dict[str, Any]]` — matches the
  `FetchPage` signature Task 8 defines (`(countrycode, rows, os_) -> (raw_body, payload)`), so it can
  be passed directly as `worldbank_pipeline_job.py`'s `fetch_page` argument at the `apps/worker` layer.

- [ ] **Step 1: Write the failing test (mirrors `test_ssrf_suite.py`'s P304 real-network test)**

```python
import pytest

from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressValidator
from packages.tender.worldbank_connector import fetch_donor_pipeline_page_live


async def _trust(conn, host: str, schemes=None) -> None:
    await register_source(conn, host=host, allowed_schemes=schemes or ["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


@pytest.mark.asyncio
async def test_live_fetch_against_real_worldbank_api(engine):
    async with engine.begin() as conn:
        await _trust(conn, "search.worldbank.org")
        validator = EgressValidator()
        raw_body, payload = await fetch_donor_pipeline_page_live(conn, validator, countrycode_exact="AZ", rows=1, os_=0)
        assert payload["projects"]
        assert int(payload["total"]) >= 1
```

Save as `tests/security/test_worldbank_live_fetch.py` (same directory as the existing P301-P304 SSRF
suite, since this is also a real-network test that must run against a genuinely reachable host).

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/security/test_worldbank_live_fetch.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_donor_pipeline_page_live'`.

- [ ] **Step 3: Add the live-fetch function to `worldbank_connector.py`**

Append to `packages/tender/worldbank_connector.py`:
```python
import json

from sqlalchemy.ext.asyncio import AsyncConnection as _AsyncConnection  # already imported above, no duplicate needed
from packages.platform.egress.fetch import fetch_via_validator
from packages.platform.egress.validator import EgressValidator


class UnexpectedResponseStatus(Exception):
    pass


async def fetch_donor_pipeline_page_live(
    conn: AsyncConnection,
    validator: EgressValidator,
    *,
    countrycode_exact: str,
    rows: int,
    os_: int,
) -> tuple[bytes, dict[str, Any]]:
    url = f"https://search.worldbank.org/api/v2/projects?format=json&countrycode_exact={countrycode_exact}&rows={rows}&os={os_}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"World Bank Projects API returned HTTP {status} for {url!r}")
    return body, json.loads(body)
```

(Adjust the actual import block at the top of the file rather than duplicating an `AsyncConnection`
import — read the file first; the two new imports `fetch_via_validator` and `EgressValidator` are the
only genuinely new ones, and `json` needs adding to the top-level imports too since Task 7's version of
this file didn't need it.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/security/test_worldbank_live_fetch.py -v`
Expected: PASS — a real HTTP request reaches `search.worldbank.org` through the full
validate-then-pinned-connect pipeline and gets a real 200 response.

If this fails with a DNS or connection error, that means `search.worldbank.org` is unreachable from
this environment right now (proxy/firewall) — not a code bug; record that in
`docs/decisions/OPEN-QUESTIONS.md` rather than weakening the test or removing egress validation.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/worldbank_connector.py tests/security/test_worldbank_live_fetch.py
git commit -m "feat(tender): live egress-validated fetch for World Bank donor-pipeline signals"
```

---

## Task 10: Regression registry, WORKLOG, and Open Questions

**Files:**
- Modify: `tests/test_regression_registry.py`
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

**Interfaces:** none (documentation/registry only).

- [ ] **Step 1: Update the regression registry**

Read `tests/test_regression_registry.py`, find the entry (or the "no phase assigned yet" section) for
`P309`, and point it at `tests/integration/test_worldbank_connector.py` (signal built and stored from a
real source) and `tests/integration/test_signals_store.py` (source+date+ttl on the stored fact) — same
"stop skipping, point at the real test" transition every other P0xx entry went through in task 1.E.

- [ ] **Step 2: Append a WORKLOG entry**

Follow the exact format of every prior entry in `docs/reports/WORKLOG.md` (date, **Сделано**, **Вывод
полного прогона** with actual `pytest`/`ruff`/`mypy`/`check_v1_untouched` output from this task's real
run, **Дальше**, **Блокеры**). State plainly: (a) this closes P309 for exactly one signal source
(World Bank donor pipeline), not the other five categories in `TENDER_INTELLIGENCE_SPEC.md` §5.2; (b)
`search.worldbank.org`'s trusted-source registration used in tests is test-scoped
(`scanner_run_reference="test-scan"`), same precedent as `etender.gov.az`'s own test-only trust —
production trust for either host is a still-open operational decision, not resolved by this task.

- [ ] **Step 3: Record open questions**

Add an entry to `docs/decisions/OPEN-QUESTIONS.md` documenting, honestly and without inventing
resolutions:
- `confidence` and `ttl_class` on `Signal` are qualitative/label fields fixed by this task's one
  connector, not a general classification scheme for every future signal source — a future source
  (e.g. a decree scraped from e-qanun.az with less structural certainty than a first-party donor API)
  will need its own tier, not reuse `"official_source"` by default.
- `object_region` for this connector is country-level only (World Bank's public API does not expose
  sub-national geography for Azerbaijan projects) — a future signal source with real regional
  granularity should not be forced into the same coarseness.
- The other five `TENDER_INTELLIGENCE_SPEC.md` §5.2 signal categories (decrees, procurement plans,
  budgets, TEO tenders, vacancies) and the other three donor institutions (ADB/EBRD/AIIB) remain
  unstarted — no phase/task document assigns them individually yet, same "not silently dropped" style
  as the `P003`/`P004` phase-assignment gap already on record in this file.

- [ ] **Step 4: Run the full gate one final time**

Run:
```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```
Expected: 0 failures, 0 ruff/mypy issues, v1-untouched PASS. Paste the real output into the WORKLOG
entry from Step 2 (do not write the entry before running this — the WORKLOG's own convention, evident
in every prior entry, is to record what actually happened, not what was expected to happen).

- [ ] **Step 5: Commit**

```bash
git add tests/test_regression_registry.py docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(tender): close out task 2.B (World Bank donor-pipeline signal ingestion)"
```

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** `TENDER_INTELLIGENCE_SPEC.md` §5.2's `P309` ("сигнал из реального распоряжения
  нормализован, привязан к объекту, имеет source+date+ttl") is satisfied for the donor-pipeline
  category specifically — Tasks 4-8 build and prove the mechanism, Task 6's `Signal.observed_at`/
  `source`/`ttl_class` are exactly the "source+date+ttl" triple, Task 6's three `object_*` fields are
  the object binding. The other five categories are explicitly deferred (Global Constraints), not
  silently skipped.
- **`INV-15`/`INV-16`/`INV-17` coverage:** `INV-15` (fact = tuple) is `Signal`'s five required fields
  (Task 6). `INV-16` (source is addressable from every derived fact) is `raw_snapshot_id` on `Signal`
  plus the existing `raw_snapshot.py` mechanism (reused, not rebuilt). `INV-17` (every fact has a TTL)
  is `ttl_class`, deliberately a label pending `TBD-TIS-01`.
- **No placeholders:** every code block above is complete and real; every example value traces to an
  actual live capture made during this task's reconnaissance (2026-08-05), not an invented one.
