# Phase 1, Task 1.A — eTender empirical-contract connector — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the eTender ingestion mechanism required by `docs/reports/PLAN-MISSION-1.md` §3 task
1.A — empirical-contract validation + schema-drift detector, raw-snapshot → normalized-version
immutable pipeline, and `identity_query_keys` — proven against two real, live-captured fixtures
(`fixtures/tender-snapshots/etender/`), not synthetic data.

**Architecture:** `packages/tender` gets a generic, source-agnostic contract/drift-detection layer
(`source_contract.py`, `schema_drift.py`) plus generic raw/normalized storage
(`raw_snapshot.py`, `normalized.py`), and one concrete eTender contract + connector function
(`etender_contract.py`, `etender_connector.py`) built directly from the two captured fixtures. The
connector always writes the raw snapshot first (evidence capture is unconditional), then checks
drift; only a drift-free response gets normalized into a new immutable `tender_versions` row.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async + `asyncpg`, PostgreSQL (via `testcontainers` in
tests, per this repo's existing `tests/integration/conftest.py`), pytest/pytest-asyncio.

## Global Constraints

- No fabricated data — the two contract fixtures are real, live, checksummed captures (see
  `fixtures/tender-snapshots/etender/MANIFEST.md`); all example values in this plan (`eventType: 7`,
  `totalItems: 4135`, `organizationVoen: "1000418451"`) are copied from those captures verbatim.
- Requirement IDs used here must trace to source docs: `FR-TND-02`, `FR-TND-10`, `INT-01`, `INT-02`,
  `DM-01`, `DM-02`, `DM-03`, `P108`. Do not invent new IDs.
- Raw snapshots are never UPDATEd by application code — a re-fetch is always a new `INSERT`.
- Scope is 1.A only: no resumable pagination, no BOQ completeness/reconciliation, no exception queue
  (those are 1.B/1.D). The BOQ fixture is used only to prove the schema-drift detector against a
  second real contract shape, not to build BOQ ingestion.
- Migration numbering continues from `0002_platform_jobs.sql` → `0003_tender_ingestion.sql`.

---

## Task 1: Migration — `raw_snapshots`, `tenders`, `tender_versions`

**Files:**
- Create: `migrations/0003_tender_ingestion.sql`
- Test: `tests/integration/test_migrations_runner.py` already asserts `apply_all()` succeeds against
  every discovered migration on an empty DB — no new test file needed, this task just needs the
  existing suite to still pass with the new migration present.

**Interfaces:**
- Produces: tables `raw_snapshots(id, source, resource_type, identity_key, checksum, body, contract_version, correlation_id, fetched_at)`,
  `tenders(id, source, identity_key, current_version_id, created_at)`,
  `tender_versions(id, tender_id, version_number, raw_snapshot_id, parser_version, normalized_fields, created_at)`.

- [ ] **Step 1: Write the migration file**

```sql
-- Tender ingestion: raw snapshots (DM-02/DM-03), tender identity anchor, and
-- normalized immutable versions (FR-TND-02, P108).
-- FR-TND-02, FR-TND-10, INT-01, INT-02, DM-02, DM-03, P108

CREATE TABLE raw_snapshots (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    resource_type TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    checksum TEXT NOT NULL,
    body JSONB NOT NULL,
    contract_version TEXT NOT NULL,
    correlation_id TEXT NOT NULL,
    fetched_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- A re-fetch always inserts a new row (DM-02) — application code never issues
-- an UPDATE against this table; there is no key to upsert on, by design.
CREATE INDEX raw_snapshots_lookup_idx ON raw_snapshots (source, resource_type, identity_key, fetched_at);

-- One authoritative identity per (source, identity_key) — DM-01.
CREATE TABLE tenders (
    id BIGSERIAL PRIMARY KEY,
    source TEXT NOT NULL,
    identity_key TEXT NOT NULL,
    current_version_id BIGINT,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (source, identity_key)
);

CREATE TABLE tender_versions (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    version_number INTEGER NOT NULL,
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    parser_version TEXT NOT NULL,
    normalized_fields JSONB NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (tender_id, version_number)
);

ALTER TABLE tenders
    ADD CONSTRAINT tenders_current_version_fk
    FOREIGN KEY (current_version_id) REFERENCES tender_versions (id);
```

- [ ] **Step 2: Run the existing migration-runner integration test to verify it still passes**

Run: `python -m pytest tests/integration/test_migrations_runner.py -q`
Expected: PASS (new migration applies cleanly on empty DB, checksum recorded in ledger).

- [ ] **Step 3: Commit**

```bash
git add migrations/0003_tender_ingestion.sql
git commit -m "feat(tender): add raw_snapshots/tenders/tender_versions migration (FR-TND-02, DM-01..03, P108)"
```

---

## Task 2: `source_contract.py` — contract + `identity_query_keys`

**Files:**
- Create: `packages/tender/source_contract.py`
- Test: `tests/unit/test_source_contract.py`

**Interfaces:**
- Produces: `FieldSpec(name: str, type: str)`, `SourceContract(name: str, identity_query_keys: tuple[str, ...], fields: tuple[FieldSpec, ...])`,
  `canonical_identity(contract: SourceContract, params: dict) -> str`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_source_contract.py
"""INT-02: identity_query_keys — a record's identity must not be lost to
naive URL/param canonicalization (RN-06: `?newsID=N` dropped by a
canonicalizer that discarded the whole query string)."""

import pytest
from packages.tender.source_contract import FieldSpec, SourceContract, canonical_identity

CONTRACT = SourceContract(
    name="etender.event_details",
    identity_query_keys=("id",),
    fields=(FieldSpec("id", "number"),),
)

PAGED_CONTRACT = SourceContract(
    name="etender.bom_lines_page",
    identity_query_keys=("event_id", "PageNumber"),
    fields=(FieldSpec("currentPage", "number"),),
)


def test_canonical_identity_uses_only_declared_keys():
    identity = canonical_identity(CONTRACT, {"id": 355920})
    assert identity == "etender.event_details|id=355920"


def test_canonical_identity_distinguishes_records_a_naive_canonicalizer_would_merge():
    # RN-06: dropping the query string entirely would merge these two.
    a = canonical_identity(CONTRACT, {"id": 355920})
    b = canonical_identity(CONTRACT, {"id": 355921})
    assert a != b


def test_canonical_identity_uses_all_identity_query_keys_for_paged_resources():
    page1 = canonical_identity(PAGED_CONTRACT, {"event_id": 355920, "PageNumber": 1})
    page2 = canonical_identity(PAGED_CONTRACT, {"event_id": 355920, "PageNumber": 2})
    assert page1 != page2


def test_canonical_identity_raises_on_missing_identity_key():
    with pytest.raises(KeyError):
        canonical_identity(CONTRACT, {})
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/unit/test_source_contract.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.source_contract'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/tender/source_contract.py
"""Source contract for an empirical (undocumented-API) connector (INT-01,
INT-02, FR-TND-10). `identity_query_keys` fixes exactly which parameters
define a record's identity for this contract, so identity is never lost to
a generic URL/query canonicalizer that doesn't know which params matter
(RN-06)."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class FieldSpec:
    name: str
    type: str  # "string" | "number" | "boolean" | "null" | "array" | "object"


@dataclass(frozen=True)
class SourceContract:
    name: str
    identity_query_keys: tuple[str, ...]
    fields: tuple[FieldSpec, ...]


def canonical_identity(contract: SourceContract, params: dict) -> str:
    parts = [f"{key}={params[key]}" for key in contract.identity_query_keys]
    return contract.name + "|" + "&".join(parts)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/unit/test_source_contract.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/source_contract.py tests/unit/test_source_contract.py
git commit -m "feat(tender): source contract + identity_query_keys (INT-02, RN-06)"
```

---

## Task 3: `schema_drift.py` — drift detector

**Files:**
- Create: `packages/tender/schema_drift.py`
- Test: `tests/unit/test_schema_drift.py`

**Interfaces:**
- Consumes: `SourceContract`, `FieldSpec` from `packages/tender/source_contract.py`.
- Produces: `SchemaDrift(added_fields: tuple[str, ...], removed_fields: tuple[str, ...], type_changed_fields: tuple[str, ...])`
  with `.has_drift: bool` property; `detect_schema_drift(contract: SourceContract, actual_payload: dict) -> SchemaDrift`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_schema_drift.py
"""FR-TND-10 / INT-02: a response-shape change must produce a detectable
drift event, never a silent field loss."""

from packages.tender.schema_drift import detect_schema_drift
from packages.tender.source_contract import FieldSpec, SourceContract

CONTRACT = SourceContract(
    name="etender.event_details",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("eventType", "number"),
        FieldSpec("cpvCode", "null"),
    ),
)

GOOD_PAYLOAD = {"id": 355920, "eventType": 7, "cpvCode": None}


def test_no_drift_on_matching_fixture():
    drift = detect_schema_drift(CONTRACT, GOOD_PAYLOAD)
    assert drift.has_drift is False


def test_detects_added_field():
    payload = {**GOOD_PAYLOAD, "newField": "surprise"}
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is True
    assert drift.added_fields == ("newField",)


def test_detects_removed_field():
    payload = {"id": 355920, "eventType": 7}  # cpvCode missing entirely
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is True
    assert drift.removed_fields == ("cpvCode",)


def test_detects_type_changed_field():
    payload = {**GOOD_PAYLOAD, "eventType": "7"}  # number -> string
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is True
    assert drift.type_changed_fields == ("eventType",)


def test_null_value_does_not_count_as_drift_for_a_typed_field():
    # A field that is normally a number can legitimately be null on some
    # records (e.g. an unpriced tender) — that is data variation, not
    # schema drift, and must not be flagged.
    payload = {**GOOD_PAYLOAD, "eventType": None}
    drift = detect_schema_drift(CONTRACT, payload)
    assert drift.has_drift is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/unit/test_schema_drift.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.schema_drift'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/tender/schema_drift.py
"""Schema-drift detector (FR-TND-10, INT-02): compares an actual response
payload's shape against its frozen SourceContract. Any added field,
removed field, or incompatible type change is reported — never silently
absorbed. A field going to `null` is data variation, not drift, and is
deliberately not flagged (a genuinely incompatible type, e.g. a number
field turning into a string, still is)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .source_contract import SourceContract


def _json_type(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "boolean"
    if isinstance(value, (int, float)):
        return "number"
    if isinstance(value, str):
        return "string"
    if isinstance(value, list):
        return "array"
    if isinstance(value, dict):
        return "object"
    raise TypeError(f"unsupported JSON value type: {type(value)!r}")


@dataclass(frozen=True)
class SchemaDrift:
    added_fields: tuple[str, ...]
    removed_fields: tuple[str, ...]
    type_changed_fields: tuple[str, ...]

    @property
    def has_drift(self) -> bool:
        return bool(self.added_fields or self.removed_fields or self.type_changed_fields)


def detect_schema_drift(contract: SourceContract, actual_payload: dict) -> SchemaDrift:
    declared = {field.name: field for field in contract.fields}
    declared_keys = set(declared.keys())
    actual_keys = set(actual_payload.keys())

    removed = tuple(sorted(declared_keys - actual_keys))
    added = tuple(sorted(actual_keys - declared_keys))

    type_changed = []
    for name in sorted(declared_keys & actual_keys):
        actual_value = actual_payload[name]
        if actual_value is None:
            continue
        if _json_type(actual_value) != declared[name].type:
            type_changed.append(name)

    return SchemaDrift(added_fields=added, removed_fields=removed, type_changed_fields=tuple(type_changed))
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/unit/test_schema_drift.py -q`
Expected: PASS (5 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/schema_drift.py tests/unit/test_schema_drift.py
git commit -m "feat(tender): schema-drift detector (FR-TND-10, INT-02)"
```

---

## Task 4: `etender_contract.py` — concrete contracts from the real fixtures

**Files:**
- Create: `packages/tender/etender_contract.py`
- Test: `tests/integration/test_etender_contract_fixtures.py`

**Interfaces:**
- Consumes: `FieldSpec`, `SourceContract` from Task 2; `detect_schema_drift` from Task 3.
- Produces: `EVENT_DETAILS_CONTRACT: SourceContract`, `BOM_LINES_PAGE_CONTRACT: SourceContract`.

- [ ] **Step 1: Write the failing test — contracts must not drift against their own captured fixtures**

```python
# tests/integration/test_etender_contract_fixtures.py
"""The frozen contracts must exactly match the real fixtures they were
built from — the fixtures are the ground truth (INT-01: empirical
contract, no official API docs)."""

import json
from pathlib import Path

from packages.tender.etender_contract import BOM_LINES_PAGE_CONTRACT, EVENT_DETAILS_CONTRACT
from packages.tender.schema_drift import detect_schema_drift

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "tender-snapshots" / "etender"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_bytes())


def test_event_details_contract_matches_real_capture():
    payload = _load("event_355920_details.raw.json")
    drift = detect_schema_drift(EVENT_DETAILS_CONTRACT, payload)
    assert drift.has_drift is False, drift


def test_event_details_capture_has_actual_field_values_from_the_live_source():
    payload = _load("event_355920_details.raw.json")
    assert payload["eventType"] == 7
    assert payload["organizationVoen"] == "1000418451"
    assert payload["estimatedAmount"] == 16922253.74


def test_bom_lines_contract_matches_real_capture():
    payload = _load("event_355920_bomlines_page1.raw.json")
    drift = detect_schema_drift(BOM_LINES_PAGE_CONTRACT, payload)
    assert drift.has_drift is False, drift


def test_bom_lines_capture_matches_documented_audit_facts():
    # uniwatch-v2-project.md: "event 355920 -> 4 135 bomLines over 42 pages"
    payload = _load("event_355920_bomlines_page1.raw.json")
    assert payload["totalItems"] == 4135
    assert payload["totalPages"] == 42
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integration/test_etender_contract_fixtures.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.etender_contract'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/tender/etender_contract.py
"""Concrete eTender source contracts (INT-01). Built directly from the
real, live-captured fixtures in fixtures/tender-snapshots/etender/ (see
MANIFEST.md) — not from official documentation, which does not exist for
this source. `budgetCategoryCode`, `cpvCode`, `recreatedFromRfxId`,
`recreatedFromEventId`, `recreatedFromDocumentNumber` were captured as
`null`; a future capture with them populated is a data variation, not
schema drift (see schema_drift.py's null-value rule)."""

from __future__ import annotations

from .source_contract import FieldSpec, SourceContract

EVENT_DETAILS_CONTRACT = SourceContract(
    name="etender.event_details",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("rfxId", "number"),
        FieldSpec("eventId", "number"),
        FieldSpec("tenderName", "string"),
        FieldSpec("organizationName", "string"),
        FieldSpec("organizationVoen", "string"),
        FieldSpec("envelopeDate", "number"),
        FieldSpec("endDate", "number"),
        FieldSpec("publishDate", "number"),
        FieldSpec("startDate", "number"),
        FieldSpec("budgetCategoryCode", "null"),
        FieldSpec("address", "string"),
        FieldSpec("cpvCode", "null"),
        FieldSpec("eventType", "number"),
        FieldSpec("isRedirectionAvailable", "boolean"),
        FieldSpec("minNumberOfSuppliers", "number"),
        FieldSpec("estimatedAmount", "number"),
        FieldSpec("recreatedFromRfxId", "null"),
        FieldSpec("recreatedFromEventId", "null"),
        FieldSpec("documentNumber", "string"),
        FieldSpec("recreatedFromDocumentNumber", "null"),
        FieldSpec("evaluatedFinalScore", "number"),
        FieldSpec("categoryCodes", "array"),
    ),
)

BOM_LINES_PAGE_CONTRACT = SourceContract(
    name="etender.bom_lines_page",
    identity_query_keys=("event_id", "PageNumber"),
    fields=(
        FieldSpec("currentPage", "number"),
        FieldSpec("totalPages", "number"),
        FieldSpec("pageSize", "number"),
        FieldSpec("itemsInPage", "number"),
        FieldSpec("totalItems", "number"),
        FieldSpec("items", "array"),
    ),
)
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integration/test_etender_contract_fixtures.py -q`
Expected: PASS (4 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_contract.py tests/integration/test_etender_contract_fixtures.py
git commit -m "feat(tender): concrete eTender contracts from real captured fixtures (INT-01)"
```

---

## Task 5: `raw_snapshot.py` — immutable raw storage

**Files:**
- Create: `packages/tender/raw_snapshot.py`
- Test: `tests/integration/test_raw_snapshot.py`

**Interfaces:**
- Produces: `RawSnapshot(id, source, resource_type, identity_key, checksum, body, contract_version, correlation_id)`,
  `checksum_of(raw_body: bytes) -> str`, `async save_raw_snapshot(conn, *, source, resource_type, identity_key, raw_body, contract_version, correlation_id) -> int`,
  `async get_raw_snapshot(conn, snapshot_id: int) -> RawSnapshot`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_raw_snapshot.py
"""DM-02/DM-03: raw evidence is immutable and checksummed; a re-fetch is
always a new row."""

import pytest

from packages.tender.raw_snapshot import checksum_of, get_raw_snapshot, save_raw_snapshot

pytestmark = pytest.mark.asyncio


async def test_save_raw_snapshot_stores_checksummed_body(db_connection):
    raw_body = b'{"id": 355920, "eventType": 7}'
    snapshot_id = await save_raw_snapshot(
        db_connection,
        source="etender",
        resource_type="etender.event_details",
        identity_key="etender.event_details|id=355920",
        raw_body=raw_body,
        contract_version="etender.event_details",
        correlation_id="corr-1",
    )

    snapshot = await get_raw_snapshot(db_connection, snapshot_id)
    assert snapshot.checksum == checksum_of(raw_body)
    assert snapshot.body == {"id": 355920, "eventType": 7}
    assert snapshot.source == "etender"


async def test_refetch_creates_a_new_row_not_an_update(db_connection):
    body_v1 = b'{"id": 355920, "eventType": 7}'
    body_v2 = b'{"id": 355920, "eventType": 7, "estimatedAmount": 16922253.74}'

    id1 = await save_raw_snapshot(
        db_connection,
        source="etender",
        resource_type="etender.event_details",
        identity_key="etender.event_details|id=355920",
        raw_body=body_v1,
        contract_version="etender.event_details",
        correlation_id="corr-1",
    )
    id2 = await save_raw_snapshot(
        db_connection,
        source="etender",
        resource_type="etender.event_details",
        identity_key="etender.event_details|id=355920",
        raw_body=body_v2,
        contract_version="etender.event_details",
        correlation_id="corr-2",
    )

    assert id1 != id2
    first_still_intact = await get_raw_snapshot(db_connection, id1)
    assert first_still_intact.checksum == checksum_of(body_v1)
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integration/test_raw_snapshot.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.raw_snapshot'`
(if `db_connection` fixture doesn't exist yet in `tests/integration/conftest.py`, check first —
this repo's existing integration tests already use a per-test connection fixture; reuse its name
rather than inventing a new one. Read `tests/integration/conftest.py` and `tests/integration/test_jobs_store.py`'s
fixture usage before writing this step for real, and rename `db_connection` in the test above to
match whatever this repo already provides.)

- [ ] **Step 3: Write minimal implementation**

```python
# packages/tender/raw_snapshot.py
"""Raw immutable evidence (DM-02, DM-03): a re-fetch always creates a new
row; application code never issues an UPDATE against raw_snapshots. The
checksum is sha256 of the exact raw bytes captured, so raw evidence is
provably unmodified end-to-end (docs/adr/0003-data-authority-and-provenance.md)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class RawSnapshot:
    id: int
    source: str
    resource_type: str
    identity_key: str
    checksum: str
    body: dict[str, Any]
    contract_version: str
    correlation_id: str


def checksum_of(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


async def save_raw_snapshot(
    conn: AsyncConnection,
    *,
    source: str,
    resource_type: str,
    identity_key: str,
    raw_body: bytes,
    contract_version: str,
    correlation_id: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO raw_snapshots
                    (source, resource_type, identity_key, checksum, body, contract_version, correlation_id)
                VALUES (:source, :resource_type, :identity_key, :checksum, CAST(:body AS jsonb),
                        :contract_version, :correlation_id)
                RETURNING id
                """
            ),
            {
                "source": source,
                "resource_type": resource_type,
                "identity_key": identity_key,
                "checksum": checksum_of(raw_body),
                "body": raw_body.decode("utf-8"),
                "contract_version": contract_version,
                "correlation_id": correlation_id,
            },
        )
    ).scalar_one()


async def get_raw_snapshot(conn: AsyncConnection, snapshot_id: int) -> RawSnapshot:
    row = (
        (
            await conn.execute(
                text(
                    """
                SELECT id, source, resource_type, identity_key, checksum, body,
                       contract_version, correlation_id
                FROM raw_snapshots WHERE id = :id
                """
                ),
                {"id": snapshot_id},
            )
        )
        .mappings()
        .one()
    )
    body = row["body"]
    if isinstance(body, str):
        body = json.loads(body)
    return RawSnapshot(
        id=row["id"],
        source=row["source"],
        resource_type=row["resource_type"],
        identity_key=row["identity_key"],
        checksum=row["checksum"],
        body=body,
        contract_version=row["contract_version"],
        correlation_id=row["correlation_id"],
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integration/test_raw_snapshot.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/raw_snapshot.py tests/integration/test_raw_snapshot.py
git commit -m "feat(tender): immutable checksummed raw snapshot storage (DM-02, DM-03)"
```

---

## Task 6: `normalized.py` — versioned normalized facts

**Files:**
- Create: `packages/tender/normalized.py`
- Test: `tests/integration/test_normalized_versioning.py`

**Interfaces:**
- Produces: `TenderVersion(id, tender_id, version_number, raw_snapshot_id, parser_version, normalized_fields)`,
  `async get_or_create_tender(conn, *, source, identity_key) -> int`,
  `async create_normalized_version(conn, *, tender_id, raw_snapshot_id, parser_version, normalized_fields) -> TenderVersion`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_normalized_versioning.py
"""FR-TND-02, P108: normalized facts are immutable versions that keep a
provenance link to their raw snapshot; a changed tender gets a new
version, the old one stays intact (P108: v1 changes were invisible to
history because details/BOM overwrote in place with COALESCE)."""

import pytest

from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot

pytestmark = pytest.mark.asyncio


async def _snapshot(db_connection, body: bytes) -> int:
    return await save_raw_snapshot(
        db_connection,
        source="etender",
        resource_type="etender.event_details",
        identity_key="etender.event_details|id=355920",
        raw_body=body,
        contract_version="etender.event_details",
        correlation_id="corr-1",
    )


async def test_get_or_create_tender_is_idempotent_per_identity(db_connection):
    id1 = await get_or_create_tender(db_connection, source="etender", identity_key="etender.event_details|id=355920")
    id2 = await get_or_create_tender(db_connection, source="etender", identity_key="etender.event_details|id=355920")
    assert id1 == id2


async def test_second_normalization_creates_a_new_version_not_an_overwrite(db_connection):
    tender_id = await get_or_create_tender(db_connection, source="etender", identity_key="etender.event_details|id=355920")
    snap1 = await _snapshot(db_connection, b'{"id": 355920, "estimatedAmount": 16922253.74}')
    snap2 = await _snapshot(db_connection, b'{"id": 355920, "estimatedAmount": 17000000.00}')

    v1 = await create_normalized_version(
        db_connection,
        tender_id=tender_id,
        raw_snapshot_id=snap1,
        parser_version="etender-v1",
        normalized_fields={"estimated_amount": 16922253.74},
    )
    v2 = await create_normalized_version(
        db_connection,
        tender_id=tender_id,
        raw_snapshot_id=snap2,
        parser_version="etender-v1",
        normalized_fields={"estimated_amount": 17000000.00},
    )

    assert v1.version_number == 1
    assert v2.version_number == 2
    # P108: the first version's own data is untouched by the second insert.
    assert v1.normalized_fields == {"estimated_amount": 16922253.74}
    assert v1.raw_snapshot_id == snap1
    assert v2.raw_snapshot_id == snap2
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integration/test_normalized_versioning.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.normalized'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/tender/normalized.py
"""Normalized fact versioning (FR-TND-02, DM-01..03, P108): every call
creates a new immutable tender_versions row — never an UPDATE of a
previous version. `tenders` holds only the identity anchor and a pointer
to the current version (DM-01: one authoritative entity for "what's
current", not a second mutable copy of version content)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class TenderVersion:
    id: int
    tender_id: int
    version_number: int
    raw_snapshot_id: int
    parser_version: str
    normalized_fields: dict[str, Any]


async def get_or_create_tender(conn: AsyncConnection, *, source: str, identity_key: str) -> int:
    existing = (
        (
            await conn.execute(
                text("SELECT id FROM tenders WHERE source = :source AND identity_key = :identity_key"),
                {"source": source, "identity_key": identity_key},
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return existing["id"]
    return (
        await conn.execute(
            text("INSERT INTO tenders (source, identity_key) VALUES (:source, :identity_key) RETURNING id"),
            {"source": source, "identity_key": identity_key},
        )
    ).scalar_one()


async def create_normalized_version(
    conn: AsyncConnection,
    *,
    tender_id: int,
    raw_snapshot_id: int,
    parser_version: str,
    normalized_fields: dict[str, Any],
) -> TenderVersion:
    next_version = (
        (
            await conn.execute(
                text("SELECT COALESCE(MAX(version_number), 0) + 1 AS n FROM tender_versions WHERE tender_id = :tender_id"),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .one()["n"]
    )

    version_id = (
        await conn.execute(
            text(
                """
                INSERT INTO tender_versions
                    (tender_id, version_number, raw_snapshot_id, parser_version, normalized_fields)
                VALUES (:tender_id, :version_number, :raw_snapshot_id, :parser_version,
                        CAST(:normalized_fields AS jsonb))
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "version_number": next_version,
                "raw_snapshot_id": raw_snapshot_id,
                "parser_version": parser_version,
                "normalized_fields": json.dumps(normalized_fields),
            },
        )
    ).scalar_one()

    await conn.execute(
        text("UPDATE tenders SET current_version_id = :version_id WHERE id = :tender_id"),
        {"version_id": version_id, "tender_id": tender_id},
    )

    return TenderVersion(
        id=version_id,
        tender_id=tender_id,
        version_number=next_version,
        raw_snapshot_id=raw_snapshot_id,
        parser_version=parser_version,
        normalized_fields=normalized_fields,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integration/test_normalized_versioning.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/normalized.py tests/integration/test_normalized_versioning.py
git commit -m "feat(tender): versioned normalized tender facts (FR-TND-02, DM-01..03, P108)"
```

---

## Task 7: `etender_connector.py` — wire it together end-to-end

**Files:**
- Create: `packages/tender/etender_connector.py`
- Test: `tests/integration/test_etender_connector.py`

**Interfaces:**
- Consumes: `SourceContract`, `canonical_identity` (Task 2); `detect_schema_drift` (Task 3);
  `EVENT_DETAILS_CONTRACT` (Task 4); `save_raw_snapshot` (Task 5);
  `get_or_create_tender`, `create_normalized_version`, `TenderVersion` (Task 6);
  `packages.platform.outbox.enqueue` (existing, 0.B).
- Produces: `SchemaDriftDetected(Exception)`, `PARSER_VERSION: str`,
  `async ingest_event_details(conn, *, contract, raw_body, payload, correlation_id) -> TenderVersion`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_etender_connector.py
"""End-to-end: real captured fixture -> raw snapshot -> normalized version,
and a synthetically-drifted copy of that same real fixture -> raw snapshot
still saved, normalization blocked, schema_drift_event enqueued (FR-TND-10)."""

import json
from pathlib import Path

import pytest
from sqlalchemy import text

from packages.tender.etender_connector import SchemaDriftDetected, ingest_event_details
from packages.tender.etender_contract import EVENT_DETAILS_CONTRACT

pytestmark = pytest.mark.asyncio

FIXTURES = Path(__file__).parent.parent.parent / "fixtures" / "tender-snapshots" / "etender"


def _load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


async def test_ingest_real_fixture_creates_raw_snapshot_and_normalized_version(db_connection):
    raw_body = _load_bytes("event_355920_details.raw.json")
    payload = json.loads(raw_body)

    version = await ingest_event_details(
        db_connection,
        contract=EVENT_DETAILS_CONTRACT,
        raw_body=raw_body,
        payload=payload,
        correlation_id="corr-real-1",
    )

    assert version.version_number == 1
    # FR-TND-10: the actual response value is used, never a requested filter value.
    assert version.normalized_fields["event_type_actual"] == 7
    assert version.normalized_fields["organization_voen"] == "1000418451"

    row = (
        (await db_connection.execute(text("SELECT checksum FROM raw_snapshots WHERE id = :id"), {"id": version.raw_snapshot_id}))
        .mappings()
        .one()
    )
    assert row["checksum"] is not None


async def test_schema_drift_blocks_normalization_but_still_saves_raw_evidence(db_connection):
    raw_body = _load_bytes("event_355920_details.raw.json")
    payload = json.loads(raw_body)
    drifted_payload = {**payload}
    del drifted_payload["eventType"]  # simulate the source silently dropping a field

    with pytest.raises(SchemaDriftDetected):
        await ingest_event_details(
            db_connection,
            contract=EVENT_DETAILS_CONTRACT,
            raw_body=raw_body,  # raw bytes still reflect the real, undrifted capture
            payload=drifted_payload,
            correlation_id="corr-drift-1",
        )

    # Raw evidence was still captured even though normalization was blocked.
    snapshot_count = (
        (await db_connection.execute(text("SELECT count(*) AS n FROM raw_snapshots WHERE correlation_id = 'corr-drift-1'")))
        .mappings()
        .one()["n"]
    )
    assert snapshot_count == 1

    # No normalized version was created for the drifted response.
    tender_count = (
        (
            await db_connection.execute(
                text("SELECT count(*) AS n FROM tenders WHERE identity_key = 'etender.event_details|id=355920'")
            )
        )
        .mappings()
        .one()["n"]
    )
    assert tender_count == 0

    drift_events = (
        (await db_connection.execute(text("SELECT payload FROM outbox WHERE event_type = 'schema_drift_event'"))).mappings().all()
    )
    assert len(drift_events) == 1
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integration/test_etender_connector.py -q`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.etender_connector'`

- [ ] **Step 3: Write minimal implementation**

```python
# packages/tender/etender_connector.py
"""eTender empirical-contract ingestion (INT-01, INT-02, FR-TND-10). Raw
evidence is captured unconditionally, before the drift check — evidence
capture must never depend on whether the connector currently understands
the shape it received. Only a drift-free response is normalized; a
drifted one is reported via the existing transactional outbox
(schema_drift_event) and raises, so nothing gets silently mapped against
a contract it no longer matches."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform import outbox

from .normalized import TenderVersion, create_normalized_version, get_or_create_tender
from .raw_snapshot import save_raw_snapshot
from .schema_drift import SchemaDrift, detect_schema_drift
from .source_contract import SourceContract, canonical_identity

PARSER_VERSION = "etender-v1"


@dataclass
class SchemaDriftDetected(Exception):
    drift: SchemaDrift

    def __str__(self) -> str:
        return f"schema drift detected: {self.drift}"


async def ingest_event_details(
    conn: AsyncConnection,
    *,
    contract: SourceContract,
    raw_body: bytes,
    payload: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    identity_key = canonical_identity(contract, {"id": payload["id"]})

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
    if drift.has_drift:
        await outbox.enqueue(
            conn,
            aggregate_type="tender_source_contract",
            aggregate_id=contract.name,
            event_type="schema_drift_event",
            payload={
                "contract": contract.name,
                "identity_key": identity_key,
                "added_fields": list(drift.added_fields),
                "removed_fields": list(drift.removed_fields),
                "type_changed_fields": list(drift.type_changed_fields),
            },
            correlation_id=correlation_id,
        )
        raise SchemaDriftDetected(drift)

    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)

    normalized_fields = {
        "tender_name": payload["tenderName"],
        "organization_name": payload["organizationName"],
        "organization_voen": payload.get("organizationVoen"),
        # FR-TND-10 / INT-01: the actual returned value decides — this
        # connector never receives or trusts a requested EventType filter
        # value, only the eventType field the source actually returned.
        "event_type_actual": payload["eventType"],
        "estimated_amount": payload.get("estimatedAmount"),
        "document_number": payload["documentNumber"],
    }

    return await create_normalized_version(
        conn,
        tender_id=tender_id,
        raw_snapshot_id=snapshot_id,
        parser_version=PARSER_VERSION,
        normalized_fields=normalized_fields,
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integration/test_etender_connector.py -q`
Expected: PASS (2 passed)

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py tests/integration/test_etender_connector.py
git commit -m "feat(tender): eTender connector wiring — drift-gated ingest (FR-TND-10, INT-01, INT-02)"
```

---

## Task 8: Full verification + WORKLOG + final commit

**Files:**
- Modify: `docs/reports/WORKLOG.md` (append)
- No new source files.

- [ ] **Step 1: Run the full test suite**

Run: `python -m pytest tests/ -q`
Expected: all previous tests still pass, plus the new tests from Tasks 1-7.

- [ ] **Step 2: Run lint/type-check/v1-untouched gates**

Run: `python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py`
Expected: all clean (0 issues).

- [ ] **Step 3: Append WORKLOG entry**

Write a new dated section to `docs/reports/WORKLOG.md` covering: requirement IDs closed
(`FR-TND-02`, `FR-TND-10`, `INT-01`, `INT-02`, `DM-01..03`, `P108` mechanism-level), the real fixture
capture (link to `fixtures/tender-snapshots/etender/MANIFEST.md`), the two `OPEN-QUESTIONS.md`
entries raised (VÖEN/amount discrepancy, list-endpoint contract not captured), full pytest output,
and explicitly that 1.B/1.C/1.D are NOT started.

- [ ] **Step 4: Final commit**

```bash
git add docs/reports/WORKLOG.md
git commit -m "docs: WORKLOG for Phase 1 task 1.A (eTender empirical-contract connector)"
```

---

## Self-Review Notes

- **Spec coverage:** empirical contract + frozen fixtures + drift detector → Tasks 2-4;
  raw snapshot immutable/checksummed → Task 5; normalized version + provenance link → Task 6;
  `identity_query_keys` → Task 2; end-to-end wiring proving FR-TND-10's "actual value, not
  requested param" rule → Task 7. Matches `PLAN-MISSION-1.md` §3 1.A exactly; no 1.B/1.C/1.D content
  included.
- **Placeholder scan:** none — every step has real code.
- **Type consistency:** `SourceContract`/`FieldSpec` (Task 2) are consumed unchanged through Tasks
  3/4/7; `TenderVersion`/`get_or_create_tender`/`create_normalized_version` (Task 6) signatures match
  their Task 7 call sites; `SchemaDrift`/`detect_schema_drift` (Task 3) match Task 7's usage.
