# Phase 4, Task 4.B — Post-submission Tracking Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** After a tender receives a `bid`/`conditional_bid` decision, keep watching it on eTender for deadline shifts and document/BOQ changes, and flag the specific BOQ lines that changed so a human knows a recalculation is needed (`TENDER_INTELLIGENCE_SPEC.md` §7.2, P317).

**Architecture:** A new recurring worker job (`packages/tender/post_submission_tracking_job.py`) re-fetches a tracked tender's `event_details` live, reuses the EXISTING immutable versioning (`create_normalized_version` already creates a new `tender_versions` row per ingest — no schema change needed for that half), diffs the new normalized fields against the previous version in memory, and — only if something changed — live-refetches all BOM-lines pages and diffs them **in memory** against the already-stored `boq_lines` rows (never re-inserting into `boq_lines`, which has no schema support for a second generation of the same `source_line_id`). Detected changes and affected lines are recorded in two new append-only tables. `apps/worker/main.py` gains its first real job-type dispatch registry (today it only ever dispatches the `example_job` stub) plus a lightweight enqueue-what's-due loop.

**Tech Stack:** Same as the rest of the repo — Python 3.12, SQLAlchemy async + raw `text()` SQL, Postgres via testcontainers for integration tests, FastAPI for the one new read route.

## Global Constraints

- **No invented endpoint.** Q&A/clarification tracking (§7.2's "ответы на вопросы участников") requires an eTender endpoint that has never been captured — do NOT build any code against a guessed shape for it (`TENDER_INTELLIGENCE_SPEC.md` §10's anti-pattern: never hardcode an external source's structure without an empirical contract). Record it as a deferred gap in `docs/decisions/OPEN-QUESTIONS.md` (Task 6) instead.
- **Poll interval is 6 hours** — an explicit owner decision made this session (not a source-document number, not invented by the agent). Use the literal constant `TENDER_WATCH_POLL_INTERVAL_HOURS = 6` with a comment naming this as the source.
- **Never mutate `boq_lines`.** It has `UNIQUE (source, event_id, source_line_id)` and no upsert path by design (`packages/tender/boq_lines_store.py`'s own docstring: "a violation should surface as a genuine error"). Re-fetched BOM-lines pages are diffed **in memory only** via `build_boq_lines` (pure function, no DB write) against the current DB rows (`list_boq_lines_by_event`) — never passed to `store_boq_lines` a second time for the same tender.
- **`tender_change_events` and `boq_line_recalc_flags` are append-only** (ADR-0003 layer 3: derived signal) — no UPDATE/DELETE against either from application code.
- **A real eTender live fetch always goes through `packages/platform/egress`** (`fetch_via_validator`), same as the two existing live-fetch wrappers (`fetch_design_tender_page_live`, `fetch_procurement_plan_page_live` in `etender_connector.py`) — never a bare `httpx`/socket call.
- **A schema-drift response is a known failure mode, not a crash** — same handling as `bom_lines_job.py`/`design_tender_job.py`: catch `SchemaDriftDetected`, record via `packages/platform/exception_queue.py::enqueue_exception` with `category="needs_human"`, and stop that tender's check for this run (no partial/guessed diff).
- **Migration number is `0015`**, filename `migrations/0015_post_submission_tracking.sql`. Bump `packages/platform/settings.py`'s `expected_schema_version` default `"14"` → `"15"`.
- **`PARSER_VERSION` in `etender_connector.py` bumps `"etender-v2"` → `"etender-v3"`** in Task 1, because `ingest_event_details`'s `normalize_fields` output shape changes again (gains `end_date`/`envelope_date`/`start_date`) — same ADR-0003 discipline already applied once this session for the `id` field.
- Every new DB-touching function takes `conn: AsyncConnection` as its first parameter and is `async def`, matching every existing store module in `packages/tender` and `packages/decision`.

---

### Task 1: Deadline fields in `ingest_event_details` + pure field-diff logic

**Files:**
- Modify: `packages/tender/etender_connector.py` (`ingest_event_details`'s `normalize_fields`, `PARSER_VERSION`)
- Create: `packages/tender/tender_change_detection.py`
- Test: `tests/integration/test_etender_connector.py` (extend existing test), `tests/unit/test_tender_change_detection.py` (new)

**Interfaces:**
- Consumes: nothing new from other tasks.
- Produces: `ingest_event_details`'s `normalized_fields` now includes `end_date`, `envelope_date`, `start_date` (raw epoch-seconds integers/`None`, taken verbatim from the payload — no timezone interpretation). `tender_change_detection.py` exports `DEADLINE_FIELDS: frozenset[str]`, `TenderFieldChange` (frozen dataclass: `field: str`, `old_value: Any`, `new_value: Any`), `diff_normalized_fields(old: dict[str, Any], new: dict[str, Any]) -> tuple[TenderFieldChange, ...]`, `classify_change_type(changes: tuple[TenderFieldChange, ...]) -> str` (returns `"deadline_shift"` if any changed field is in `DEADLINE_FIELDS`, else `"document_changed"` — caller only calls this when `changes` is non-empty).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_tender_change_detection.py
from __future__ import annotations

from packages.tender.tender_change_detection import (
    DEADLINE_FIELDS,
    TenderFieldChange,
    classify_change_type,
    diff_normalized_fields,
)


def test_diff_normalized_fields_returns_empty_for_identical_dicts():
    old = {"id": 355920, "end_date": 1788354059, "document_number": "DOC-1"}
    new = dict(old)
    assert diff_normalized_fields(old, new) == ()


def test_diff_normalized_fields_reports_a_changed_value():
    old = {"id": 355920, "end_date": 1788354059}
    new = {"id": 355920, "end_date": 1790000000}
    result = diff_normalized_fields(old, new)
    assert result == (TenderFieldChange(field="end_date", old_value=1788354059, new_value=1790000000),)


def test_diff_normalized_fields_reports_a_key_added_in_new():
    old = {"id": 355920}
    new = {"id": 355920, "document_number": "DOC-2"}
    result = diff_normalized_fields(old, new)
    assert result == (TenderFieldChange(field="document_number", old_value=None, new_value="DOC-2"),)


def test_diff_normalized_fields_reports_a_key_removed_in_new():
    old = {"id": 355920, "document_number": "DOC-1"}
    new = {"id": 355920}
    result = diff_normalized_fields(old, new)
    assert result == (TenderFieldChange(field="document_number", old_value="DOC-1", new_value=None),)


def test_diff_normalized_fields_ignores_the_id_field():
    # "id" is the bridge key added for C1 (Task 4.A) -- it never legitimately
    # "changes" for the same tender and must never itself trigger a
    # tender_change_event.
    old = {"id": 355920, "document_number": "DOC-1"}
    new = {"id": 999999, "document_number": "DOC-1"}
    assert diff_normalized_fields(old, new) == ()


def test_classify_change_type_deadline_shift_when_a_deadline_field_changed():
    changes = (TenderFieldChange(field="end_date", old_value=1, new_value=2),)
    assert classify_change_type(changes) == "deadline_shift"


def test_classify_change_type_document_changed_for_a_non_deadline_field():
    changes = (TenderFieldChange(field="document_number", old_value="A", new_value="B"),)
    assert classify_change_type(changes) == "document_changed"


def test_classify_change_type_deadline_shift_wins_when_both_kinds_changed():
    changes = (
        TenderFieldChange(field="document_number", old_value="A", new_value="B"),
        TenderFieldChange(field="end_date", old_value=1, new_value=2),
    )
    assert classify_change_type(changes) == "deadline_shift"


def test_deadline_fields_are_exactly_the_three_date_fields():
    assert DEADLINE_FIELDS == frozenset({"end_date", "envelope_date", "start_date"})
```

```python
# tests/integration/test_etender_connector.py -- add this assertion inside the
# existing test_ingest_real_fixture_creates_raw_snapshot_and_normalized_version
# (do not duplicate the whole test -- add these three lines after the
# existing normalized_fields assertions):
    assert version.normalized_fields["end_date"] == payload["endDate"]
    assert version.normalized_fields["envelope_date"] == payload["envelopeDate"]
    assert version.normalized_fields["start_date"] == payload["startDate"]
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_tender_change_detection.py -q` — expected FAIL (`ModuleNotFoundError`).
Run: `python -m pytest tests/integration/test_etender_connector.py::test_ingest_real_fixture_creates_raw_snapshot_and_normalized_version -q` — expected FAIL (`KeyError: 'end_date'`).

- [ ] **Step 3: Implement**

In `packages/tender/etender_connector.py`, change `PARSER_VERSION = "etender-v2"` to:

```python
PARSER_VERSION = "etender-v3"
# v3 (Task 4.B): ingest_event_details's normalized_fields gained
# end_date/envelope_date/start_date -- needed to detect a deadline shift on
# re-ingestion (TENDER_INTELLIGENCE_SPEC.md §7.2, P317). Raw epoch-seconds
# integers, taken verbatim -- no timezone interpretation invented here.
```

In `ingest_event_details`'s `normalize_fields`, add three keys (after `"id": p["id"],`):

```python
            "end_date": p.get("endDate"),
            "envelope_date": p.get("envelopeDate"),
            "start_date": p.get("startDate"),
```

Create `packages/tender/tender_change_detection.py`:

```python
"""Pure diff logic for detecting a tracked tender's event_details changing
between two ingested tender_versions (Task 4.B, TENDER_INTELLIGENCE_SPEC.md
§7.2, P317). No DB access here -- packages/tender/post_submission_tracking_job.py
loads the two normalized_fields dicts and calls into this module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEADLINE_FIELDS = frozenset({"end_date", "envelope_date", "start_date"})

# "id" is the numeric event id bridge added for Task 4.A's C1 fix -- it is
# the tender's own stable identity, not a fact about the tender that could
# legitimately "change" between two versions of the SAME tender, so a diff
# must never report it (it would falsely look like a change on the rare
# occasion a caller compares fields across two different tenders by mistake).
_IGNORED_FIELDS = frozenset({"id"})


@dataclass(frozen=True)
class TenderFieldChange:
    field: str
    old_value: Any
    new_value: Any


def diff_normalized_fields(old: dict[str, Any], new: dict[str, Any]) -> tuple[TenderFieldChange, ...]:
    keys = (set(old) | set(new)) - _IGNORED_FIELDS
    changes = [
        TenderFieldChange(field=key, old_value=old.get(key), new_value=new.get(key))
        for key in sorted(keys)
        if old.get(key) != new.get(key)
    ]
    return tuple(changes)


def classify_change_type(changes: tuple[TenderFieldChange, ...]) -> str:
    if any(change.field in DEADLINE_FIELDS for change in changes):
        return "deadline_shift"
    return "document_changed"
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_tender_change_detection.py tests/integration/test_etender_connector.py -q`
Expected: all PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py packages/tender/tender_change_detection.py tests/unit/test_tender_change_detection.py tests/integration/test_etender_connector.py
git commit -m "feat(tender): deadline fields in event_details normalization, pure field-diff (task 4.B)"
```

---

### Task 2: Pure BOQ-line diff logic

**Files:**
- Create: `packages/tender/boq_line_diff.py`
- Test: `tests/unit/test_boq_line_diff.py`

**Interfaces:**
- Consumes: `packages.tender.boq_line_model.BoqLine` (existing, unchanged).
- Produces: `diff_boq_lines(old: list[BoqLine], new: list[BoqLine]) -> tuple[int, ...]` — sorted tuple of `source_line_id`s that were added in `new`, removed from `old`, or whose `description`/`unit_raw`/`qty`/`rate`/`amount` differ between the two. Task 5 calls this with `old` = current DB rows (`list_boq_lines_by_event`) and `new` = a fresh live re-fetch (never stored).

- [ ] **Step 1: Write the failing tests**

```python
# tests/unit/test_boq_line_diff.py
from __future__ import annotations

from decimal import Decimal

from packages.tender.boq_line_diff import diff_boq_lines
from packages.tender.boq_line_model import BoqLine


def _line(source_line_id: int, **overrides) -> BoqLine:
    defaults = dict(
        source_line_id=source_line_id,
        page_number=1,
        section=None,
        category_code=None,
        description="rebar-12mm",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )
    defaults.update(overrides)
    return BoqLine(**defaults)


def test_diff_boq_lines_empty_for_identical_sets():
    lines = [_line(1), _line(2)]
    assert diff_boq_lines(lines, list(lines)) == ()


def test_diff_boq_lines_detects_a_changed_quantity():
    old = [_line(1, qty=Decimal("10"))]
    new = [_line(1, qty=Decimal("15"))]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_a_changed_amount():
    old = [_line(1, amount=Decimal("8500"))]
    new = [_line(1, amount=Decimal("9000"))]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_a_changed_description():
    old = [_line(1, description="rebar-12mm")]
    new = [_line(1, description="rebar-14mm")]
    assert diff_boq_lines(old, new) == (1,)


def test_diff_boq_lines_detects_an_added_line():
    old = [_line(1)]
    new = [_line(1), _line(2)]
    assert diff_boq_lines(old, new) == (2,)


def test_diff_boq_lines_detects_a_removed_line():
    old = [_line(1), _line(2)]
    new = [_line(1)]
    assert diff_boq_lines(old, new) == (2,)


def test_diff_boq_lines_result_is_sorted():
    old = []
    new = [_line(5), _line(1), _line(3)]
    assert diff_boq_lines(old, new) == (1, 3, 5)


def test_diff_boq_lines_ignores_unit_canonical_and_status_and_page_number():
    # unit_canonical/unit_status/page_number are derived/positional, not
    # substantive content -- a line that only differs there (e.g. a
    # re-canonicalization improvement) is not a real BOQ change.
    old = [_line(1, unit_canonical="t", unit_status="mapped", page_number=1)]
    new = [_line(1, unit_canonical=None, unit_status="unmapped", page_number=2)]
    assert diff_boq_lines(old, new) == ()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/unit/test_boq_line_diff.py -q` — expected FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

Create `packages/tender/boq_line_diff.py`:

```python
"""Pure in-memory diff between two BOQ-line snapshots of the same tender
event (Task 4.B, TENDER_INTELLIGENCE_SPEC.md §7.2, P317). Never writes to
`boq_lines` -- that table has no schema support for a second generation of
the same source_line_id (UNIQUE (source, event_id, source_line_id), no
upsert). Callers pass the CURRENT DB rows as `old` and a fresh, never-stored
live re-fetch as `new`."""

from __future__ import annotations

from .boq_line_model import BoqLine

_COMPARED_FIELDS = ("description", "unit_raw", "qty", "rate", "amount")


def _fingerprint(line: BoqLine) -> tuple:
    return tuple(getattr(line, field) for field in _COMPARED_FIELDS)


def diff_boq_lines(old: list[BoqLine], new: list[BoqLine]) -> tuple[int, ...]:
    old_by_id = {line.source_line_id: line for line in old}
    new_by_id = {line.source_line_id: line for line in new}
    changed = {
        source_line_id
        for source_line_id in set(old_by_id) | set(new_by_id)
        if source_line_id not in old_by_id
        or source_line_id not in new_by_id
        or _fingerprint(old_by_id[source_line_id]) != _fingerprint(new_by_id[source_line_id])
    }
    return tuple(sorted(changed))
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/unit/test_boq_line_diff.py -q` — expected PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/boq_line_diff.py tests/unit/test_boq_line_diff.py
git commit -m "feat(tender): pure in-memory BOQ-line diff (task 4.B)"
```

---

### Task 3: Migration + persistence for change events, recalc flags, watch state

**Files:**
- Create: `migrations/0015_post_submission_tracking.sql`
- Create: `packages/tender/change_tracking_store.py`
- Modify: `packages/platform/settings.py` (`expected_schema_version` default `"14"` → `"15"`)
- Test: `tests/integration/test_change_tracking_store.py`

**Interfaces:**
- Consumes: nothing new from other tasks (uses `tenders` from `packages/tender/normalized.py`, already exists).
- Produces (used by Task 5/6):
  - `store_tender_change_event(conn, *, tender_id: int, change_type: str, changed_fields: tuple[TenderFieldChange, ...], detected_at: str, raw_snapshot_id: int) -> int`
  - `store_boq_line_recalc_flag(conn, *, tender_id: int, boqline_source_line_id: int, change_event_id: int, flagged_at: str) -> int`
  - `list_unresolved_recalc_flags(conn, *, tender_id: int) -> list[dict[str, Any]]`
  - `get_watch_state(conn, *, tender_id: int) -> str | None` (returns `last_checked_at` ISO string or `None` if never checked)
  - `upsert_watch_state(conn, *, tender_id: int, checked_at: str) -> None`

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_change_tracking_store.py
from __future__ import annotations

from packages.tender.change_tracking_store import (
    get_watch_state,
    list_unresolved_recalc_flags,
    store_boq_line_recalc_flag,
    store_tender_change_event,
    upsert_watch_state,
)
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot
from packages.tender.tender_change_detection import TenderFieldChange


async def _make_tender(conn, identity_key: str) -> int:
    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type="etender.event_details",
        identity_key=identity_key,
        raw_body=b"{}",
        contract_version="etender.event_details",
        correlation_id="test-4b-store",
    )
    tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)
    await create_normalized_version(
        conn, tender_id=tender_id, raw_snapshot_id=snapshot_id, parser_version="v1", normalized_fields={}
    )
    return tender_id, snapshot_id


async def test_store_and_list_a_recalc_flag(engine):
    async with engine.begin() as conn:
        tender_id, snapshot_id = await _make_tender(conn, "test-4b-store-1")
        change_event_id = await store_tender_change_event(
            conn,
            tender_id=tender_id,
            change_type="deadline_shift",
            changed_fields=(TenderFieldChange(field="end_date", old_value=1, new_value=2),),
            detected_at="2026-08-09T00:00:00+00:00",
            raw_snapshot_id=snapshot_id,
        )
        await store_boq_line_recalc_flag(
            conn,
            tender_id=tender_id,
            boqline_source_line_id=501,
            change_event_id=change_event_id,
            flagged_at="2026-08-09T00:00:00+00:00",
        )
        flags = await list_unresolved_recalc_flags(conn, tender_id=tender_id)

    assert len(flags) == 1
    assert flags[0]["boqline_source_line_id"] == 501
    assert flags[0]["change_event_id"] == change_event_id


async def test_list_unresolved_recalc_flags_is_scoped_to_the_tender(engine):
    async with engine.begin() as conn:
        tender_a, snap_a = await _make_tender(conn, "test-4b-store-2a")
        tender_b, snap_b = await _make_tender(conn, "test-4b-store-2b")
        event_a = await store_tender_change_event(
            conn,
            tender_id=tender_a,
            change_type="document_changed",
            changed_fields=(),
            detected_at="2026-08-09T00:00:00+00:00",
            raw_snapshot_id=snap_a,
        )
        await store_boq_line_recalc_flag(
            conn, tender_id=tender_a, boqline_source_line_id=1, change_event_id=event_a, flagged_at="2026-08-09T00:00:00+00:00"
        )

    async with engine.begin() as conn:
        flags_b = await list_unresolved_recalc_flags(conn, tender_id=tender_b)
    assert flags_b == []


async def test_watch_state_is_none_before_any_check(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-store-3")
        result = await get_watch_state(conn, tender_id=tender_id)
    assert result is None


async def test_upsert_watch_state_then_get_returns_the_latest_checked_at(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-store-4")
        await upsert_watch_state(conn, tender_id=tender_id, checked_at="2026-08-09T00:00:00+00:00")
        first = await get_watch_state(conn, tender_id=tender_id)
        await upsert_watch_state(conn, tender_id=tender_id, checked_at="2026-08-09T06:00:00+00:00")
        second = await get_watch_state(conn, tender_id=tender_id)

    assert first == "2026-08-09T00:00:00+00:00"
    assert second == "2026-08-09T06:00:00+00:00"
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/integration/test_change_tracking_store.py -q` — expected FAIL (`ModuleNotFoundError`, table doesn't exist).

- [ ] **Step 3: Implement**

Create `migrations/0015_post_submission_tracking.sql`:

```sql
-- Post-submission tracking (Phase 4, task 4.B, TENDER_INTELLIGENCE_SPEC.md
-- §7.2, P317): once a tender has a Bid/Conditional Bid decision, a
-- recurring worker job (packages/tender/post_submission_tracking_job.py)
-- re-checks it on eTender for deadline shifts and document/BOQ changes.
-- tender_change_events and boq_line_recalc_flags are both append-only
-- (ADR-0003 layer 3: derived signal) -- application code never issues an
-- UPDATE/DELETE against either. tender_watch_state is the one mutable
-- table here: a per-tender operational high-water-mark, not a fact or a
-- human decision.

CREATE TABLE tender_change_events (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    change_type TEXT NOT NULL CHECK (change_type IN ('deadline_shift', 'document_changed')),
    changed_fields JSONB NOT NULL,
    detected_at TIMESTAMPTZ NOT NULL,
    raw_snapshot_id BIGINT NOT NULL REFERENCES raw_snapshots (id),
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX tender_change_events_tender_idx ON tender_change_events (tender_id);

-- P317: "the affected BOQ lines are marked as needing recalculation".
-- resolved_at stays NULL until something explicitly resolves it -- this
-- migration does not decide who/what does that (docs/decisions/OPEN-QUESTIONS.md).
CREATE TABLE boq_line_recalc_flags (
    id BIGSERIAL PRIMARY KEY,
    tender_id BIGINT NOT NULL REFERENCES tenders (id),
    boqline_source_line_id BIGINT NOT NULL,
    change_event_id BIGINT NOT NULL REFERENCES tender_change_events (id),
    flagged_at TIMESTAMPTZ NOT NULL,
    resolved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX boq_line_recalc_flags_tender_idx ON boq_line_recalc_flags (tender_id) WHERE resolved_at IS NULL;

-- One row per tracked tender; last_checked_at is the poll job's own
-- high-water-mark (packages/tender/change_tracking_store.py's
-- upsert_watch_state), not a fact about the tender itself.
CREATE TABLE tender_watch_state (
    tender_id BIGINT PRIMARY KEY REFERENCES tenders (id),
    last_checked_at TIMESTAMPTZ NOT NULL
);
```

In `packages/platform/settings.py`, change:
```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "14")))
```
to:
```python
    expected_schema_version: int = field(default_factory=lambda: int(os.environ.get("EXPECTED_SCHEMA_VERSION", "15")))
```

Create `packages/tender/change_tracking_store.py`:

```python
"""Persistence for Task 4.B's post-submission tracking (Phase 4,
TENDER_INTELLIGENCE_SPEC.md §7.2, P317). tender_change_events and
boq_line_recalc_flags are append-only -- no UPDATE/DELETE against either
from this module. tender_watch_state is the one mutable table (an
operational high-water-mark, not a fact or a human decision)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from .tender_change_detection import TenderFieldChange


async def store_tender_change_event(
    conn: AsyncConnection,
    *,
    tender_id: int,
    change_type: str,
    changed_fields: tuple[TenderFieldChange, ...],
    detected_at: str,
    raw_snapshot_id: int,
) -> int:
    changed_fields_json = json.dumps(
        [{"field": c.field, "old_value": c.old_value, "new_value": c.new_value} for c in changed_fields]
    )
    return (
        await conn.execute(
            text(
                """
                INSERT INTO tender_change_events
                    (tender_id, change_type, changed_fields, detected_at, raw_snapshot_id)
                VALUES (:tender_id, :change_type, CAST(:changed_fields AS jsonb), :detected_at, :raw_snapshot_id)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "change_type": change_type,
                "changed_fields": changed_fields_json,
                "detected_at": detected_at,
                "raw_snapshot_id": raw_snapshot_id,
            },
        )
    ).scalar_one()


async def store_boq_line_recalc_flag(
    conn: AsyncConnection,
    *,
    tender_id: int,
    boqline_source_line_id: int,
    change_event_id: int,
    flagged_at: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO boq_line_recalc_flags
                    (tender_id, boqline_source_line_id, change_event_id, flagged_at)
                VALUES (:tender_id, :boqline_source_line_id, :change_event_id, :flagged_at)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "boqline_source_line_id": boqline_source_line_id,
                "change_event_id": change_event_id,
                "flagged_at": flagged_at,
            },
        )
    ).scalar_one()


async def list_unresolved_recalc_flags(conn: AsyncConnection, *, tender_id: int) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, boqline_source_line_id, change_event_id, flagged_at
                    FROM boq_line_recalc_flags
                    WHERE tender_id = :tender_id AND resolved_at IS NULL
                    ORDER BY flagged_at, id
                    """
                ),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .all()
    )
    return [dict(row) for row in rows]


async def get_watch_state(conn: AsyncConnection, *, tender_id: int) -> str | None:
    row = (
        await conn.execute(
            text("SELECT last_checked_at FROM tender_watch_state WHERE tender_id = :tender_id"), {"tender_id": tender_id}
        )
    ).first()
    if row is None:
        return None
    return row[0].isoformat()


async def upsert_watch_state(conn: AsyncConnection, *, tender_id: int, checked_at: str) -> None:
    await conn.execute(
        text(
            """
            INSERT INTO tender_watch_state (tender_id, last_checked_at)
            VALUES (:tender_id, :checked_at)
            ON CONFLICT (tender_id) DO UPDATE SET last_checked_at = EXCLUDED.last_checked_at
            """
        ),
        {"tender_id": tender_id, "checked_at": checked_at},
    )
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/integration/test_change_tracking_store.py -q` — expected PASS.
Also run: `python -m pytest tests/ -q -m "not live_network"` to confirm the schema-version bump didn't break any test hardcoding `expected_schema_version=14` (grep first: `grep -rn "expected_schema_version=14" tests/` — every hit must be updated to `15` as part of this step, since a stale hardcoded version fails `assert_schema_up_to_date()` in any test that starts a real app).

- [ ] **Step 5: Commit**

```bash
git add migrations/0015_post_submission_tracking.sql packages/platform/settings.py packages/tender/change_tracking_store.py tests/integration/test_change_tracking_store.py
# also add any test file touched to fix a hardcoded expected_schema_version=14
git commit -m "feat(tender): migration + store for tender_change_events/boq_line_recalc_flags/tender_watch_state (task 4.B), schema version 14->15"
```

---

### Task 4: Which tenders to watch, and which are due

**Files:**
- Modify: `packages/decision/decision_store.py` (add one function)
- Modify: `packages/tender/change_tracking_store.py` (add one function)
- Test: `tests/integration/test_decision_store.py` (extend), `tests/integration/test_change_tracking_store.py` (extend)

**Interfaces:**
- Consumes: `decisions` table (existing), `tender_watch_state` (Task 3).
- Produces: `packages.decision.decision_store.list_tenders_with_active_bid_decision(conn) -> list[int]` — distinct `tender_id`s whose MOST RECENT decision (by `decided_at`) is `bid` or `conditional_bid`. `packages.tender.change_tracking_store.list_tenders_due_for_check(conn, *, tender_ids: list[int], now: str, interval_hours: int) -> list[int]` — filters `tender_ids` down to those never checked (`tender_watch_state` has no row) or last checked more than `interval_hours` before `now`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_decision_store.py -- add "list_tenders_with_active_bid_decision"
# to the existing "from packages.decision.decision_store import (...)" block,
# and add these two tests (they reuse this file's own _make_tender helper,
# already defined above the existing tests):


def _decision(tender_id: int, decision_type: str, decided_at: str) -> Decision:
    return Decision(
        tender_id=tender_id,
        decision_type=decision_type,
        conditions=(),
        deadline=None,
        justification="test",
        actor="pm-1",
        decided_at=decided_at,
        go_no_go_inputs_id=None,
        bid_readiness_candidate_id=None,
    )


async def test_list_tenders_with_active_bid_decision_returns_bid_and_conditional_bid(engine):
    async with engine.begin() as conn:
        tender_a = await _make_tender(conn, "test-decision-store-active-a")
        tender_b = await _make_tender(conn, "test-decision-store-active-b")
        tender_c = await _make_tender(conn, "test-decision-store-active-c")
        await store_decision(conn, _decision(tender_a, "bid", "2026-08-09T00:00:00+00:00"))
        await store_decision(conn, _decision(tender_b, "conditional_bid", "2026-08-09T00:00:00+00:00"))
        await store_decision(conn, _decision(tender_c, "no_go", "2026-08-09T00:00:00+00:00"))

        result = await list_tenders_with_active_bid_decision(conn)

    assert tender_a in result
    assert tender_b in result
    assert tender_c not in result


async def test_list_tenders_with_active_bid_decision_uses_the_most_recent_decision(engine):
    async with engine.begin() as conn:
        tender_id = await _make_tender(conn, "test-decision-store-active-superseded")
        await store_decision(conn, _decision(tender_id, "bid", "2026-08-01T00:00:00+00:00"))
        # Append-only: a later row records the bid being abandoned. The
        # LATEST decision by decided_at must win, not the first one stored.
        await store_decision(conn, _decision(tender_id, "no_go", "2026-08-09T00:00:00+00:00"))

        result = await list_tenders_with_active_bid_decision(conn)

    assert tender_id not in result
```

```python
# tests/integration/test_change_tracking_store.py -- add these tests
from packages.tender.change_tracking_store import list_tenders_due_for_check


async def test_list_tenders_due_for_check_includes_a_never_checked_tender(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-due-1")
        result = await list_tenders_due_for_check(conn, tender_ids=[tender_id], now="2026-08-09T12:00:00+00:00", interval_hours=6)
    assert result == [tender_id]


async def test_list_tenders_due_for_check_excludes_a_recently_checked_tender(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-due-2")
        await upsert_watch_state(conn, tender_id=tender_id, checked_at="2026-08-09T10:00:00+00:00")
        result = await list_tenders_due_for_check(conn, tender_ids=[tender_id], now="2026-08-09T12:00:00+00:00", interval_hours=6)
    assert result == []


async def test_list_tenders_due_for_check_includes_a_tender_checked_over_the_interval_ago(engine):
    async with engine.begin() as conn:
        tender_id, _snap = await _make_tender(conn, "test-4b-due-3")
        await upsert_watch_state(conn, tender_id=tender_id, checked_at="2026-08-09T00:00:00+00:00")
        result = await list_tenders_due_for_check(conn, tender_ids=[tender_id], now="2026-08-09T12:00:00+00:00", interval_hours=6)
    assert result == [tender_id]
```
(Add `from packages.tender.change_tracking_store import upsert_watch_state` to this test file's imports if not already present from Task 3.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integration/test_decision_store.py tests/integration/test_change_tracking_store.py -q` — expected FAIL (`ImportError`/`AttributeError`).

- [ ] **Step 3: Implement**

In `packages/decision/decision_store.py`, add (near `list_lock_in_requirements_by_tender`):

```python
async def list_tenders_with_active_bid_decision(conn: AsyncConnection) -> list[int]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                SELECT DISTINCT ON (tender_id) tender_id, decision_type
                FROM decisions
                ORDER BY tender_id, decided_at DESC, id DESC
                """
                )
            )
        )
        .mappings()
        .all()
    )
    return [row["tender_id"] for row in rows if row["decision_type"] in ("bid", "conditional_bid")]
```

In `packages/tender/change_tracking_store.py`, add:

```python
async def list_tenders_due_for_check(conn: AsyncConnection, *, tender_ids: list[int], now: str, interval_hours: int) -> list[int]:
    if not tender_ids:
        return []
    rows = (
        await conn.execute(
            text(
                """
                SELECT t.id AS tender_id
                FROM unnest(CAST(:tender_ids AS bigint[])) AS t(id)
                LEFT JOIN tender_watch_state w ON w.tender_id = t.id
                WHERE w.last_checked_at IS NULL
                   OR w.last_checked_at <= CAST(:now AS timestamptz) - make_interval(hours => :interval_hours)
                ORDER BY t.id
                """
            ),
            {"tender_ids": tender_ids, "now": now, "interval_hours": interval_hours},
        )
    ).all()
    return [row[0] for row in rows]
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integration/test_decision_store.py tests/integration/test_change_tracking_store.py -q` — expected PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/decision/decision_store.py packages/tender/change_tracking_store.py tests/integration/test_decision_store.py tests/integration/test_change_tracking_store.py
git commit -m "feat(decision,tender): query active-bid tenders and which are due for a post-submission check (task 4.B)"
```

---

### Task 5: Live-fetch wrappers + the tracking job itself

**Files:**
- Modify: `packages/tender/etender_connector.py` (add two live-fetch wrappers)
- Create: `packages/tender/post_submission_tracking_job.py`
- Test: `tests/integration/test_post_submission_tracking_job.py`

**Interfaces:**
- Consumes: `get_event_id_for_tender`, `get_current_tender_version_id` (`normalized.py`, existing), `ingest_event_details` (existing, now with deadline fields from Task 1), `diff_normalized_fields`/`classify_change_type` (Task 1), `build_boq_lines` (existing, pure), `list_boq_lines_by_event` (existing), `diff_boq_lines` (Task 2), `store_tender_change_event`/`store_boq_line_recalc_flag`/`upsert_watch_state` (Task 3).
- Produces: `fetch_event_details_live(conn, validator, *, event_id: int) -> tuple[bytes, dict]`, `fetch_bom_lines_page_live(conn, validator, *, event_id: int, page_number: int) -> tuple[bytes, dict]` in `etender_connector.py`. `packages.tender.post_submission_tracking_job.check_tender_for_changes(conn, *, tender_id: int, fetch_event_details, fetch_bom_page, correlation_id: str, observed_at: str) -> dict[str, Any]` — a single-shot (no multi-step checkpoint needed; bounded by one tender's own page count) check: returns `{"change_detected": bool, "change_type": str | None, "flagged_line_count": int}`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_post_submission_tracking_job.py
from __future__ import annotations

import json
from decimal import Decimal

from packages.tender.boq_line_model import BoqLine
from packages.tender.boq_lines_store import store_boq_lines
from packages.tender.change_tracking_store import get_watch_state, list_unresolved_recalc_flags
from packages.tender.etender_connector import ingest_bom_lines_page, ingest_event_details
from packages.tender.normalized import get_or_create_tender
from packages.tender.post_submission_tracking_job import check_tender_for_changes


def _details_payload(event_id: int, end_date: int, document_number: str = "DOC-1") -> dict:
    return {
        "id": event_id,
        "tenderName": "Test tender",
        "organizationName": "Test org",
        "organizationVoen": "1000000000",
        "eventType": 7,
        "estimatedAmount": 100000,
        "documentNumber": document_number,
        "endDate": end_date,
        "envelopeDate": end_date,
        "startDate": end_date - 1000,
    }


def _bom_page_payload(event_id: int, current_page: int, total_pages: int, items: list[dict]) -> dict:
    return {
        "currentPage": current_page,
        "totalPages": total_pages,
        "totalItems": len(items),
        "itemsInPage": len(items),
        "items": items,
    }


def _bom_item(item_id: int, qty: float = 10.0, description: str = "rebar-12mm") -> dict:
    return {
        "id": item_id,
        "name": None,
        "categoryCode": None,
        "description": description,
        "unitOfMeasure": "t",
        "quantity": qty,
        "rate": 850,
        "amount": 850 * qty,
    }


async def test_no_change_detected_when_refetch_is_identical(engine):
    event_id = 700001
    async with engine.begin() as conn:
        await ingest_event_details(
            conn, raw_body=b"{}", payload=_details_payload(event_id, end_date=1788354059), correlation_id="test-4b-job-1"
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")

    async def fetch_event_details(eid):
        assert eid == event_id
        payload = _details_payload(event_id, end_date=1788354059)
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        raise AssertionError("must not be called when event_details didn't change")

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-1",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result["change_detected"] is False
    assert result["flagged_line_count"] == 0

    async with engine.begin() as conn:
        watch_state = await get_watch_state(conn, tender_id=tender_id)
    assert watch_state == "2026-08-09T12:00:00+00:00"


async def test_deadline_shift_detected_and_recorded(engine):
    event_id = 700002
    async with engine.begin() as conn:
        await ingest_event_details(
            conn, raw_body=b"{}", payload=_details_payload(event_id, end_date=1788354059), correlation_id="test-4b-job-2"
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")

    async def fetch_event_details(eid):
        payload = _details_payload(event_id, end_date=1790000000)
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        payload = _bom_page_payload(event_id, page_number, total_pages=1, items=[_bom_item(1)])
        return json.dumps(payload).encode("utf-8"), payload

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-2",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result["change_detected"] is True
    assert result["change_type"] == "deadline_shift"


async def test_boq_line_change_is_flagged_without_mutating_boq_lines(engine):
    event_id = 700003
    async with engine.begin() as conn:
        await ingest_event_details(
            conn,
            raw_body=b"{}",
            payload=_details_payload(event_id, end_date=1788354059, document_number="DOC-1"),
            correlation_id="test-4b-job-3",
        )
        tender_id = await get_or_create_tender(conn, source="etender", identity_key=f"etender.event_details|id={event_id}")
        version = await ingest_bom_lines_page(
            conn,
            event_id=event_id,
            raw_body=b"{}",
            payload=_bom_page_payload(event_id, 1, 1, [_bom_item(501, qty=10.0)]),
            correlation_id="test-4b-job-3",
        )
        line = BoqLine(
            source_line_id=501,
            page_number=1,
            section=None,
            category_code=None,
            description="rebar-12mm",
            unit_raw="t",
            unit_canonical="t",
            unit_status="mapped",
            qty=Decimal("10"),
            line_type="normal",
            spec_requirements=(),
            rate=Decimal("850"),
            amount=Decimal("8500"),
        )
        await store_boq_lines(
            conn,
            source="etender",
            event_id=event_id,
            tender_version_id=version.id,
            raw_snapshot_id=version.raw_snapshot_id,
            lines=[line],
        )

    async def fetch_event_details(eid):
        # document_number changed -> triggers a re-walk of BOM pages
        payload = _details_payload(event_id, end_date=1788354059, document_number="DOC-2")
        return json.dumps(payload).encode("utf-8"), payload

    async def fetch_bom_page(eid, page_number):
        payload = _bom_page_payload(event_id, page_number, total_pages=1, items=[_bom_item(501, qty=15.0)])
        return json.dumps(payload).encode("utf-8"), payload

    async with engine.begin() as conn:
        result = await check_tender_for_changes(
            conn,
            tender_id=tender_id,
            fetch_event_details=fetch_event_details,
            fetch_bom_page=fetch_bom_page,
            correlation_id="test-4b-job-3",
            observed_at="2026-08-09T12:00:00+00:00",
        )

    assert result["flagged_line_count"] == 1

    async with engine.begin() as conn:
        flags = await list_unresolved_recalc_flags(conn, tender_id=tender_id)
        # boq_lines itself must be untouched -- still exactly the ORIGINAL
        # qty=10, never overwritten by the live re-fetch's qty=15.
        from packages.tender.boq_lines_store import list_boq_lines_by_event

        stored_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id)

    assert [f["boqline_source_line_id"] for f in flags] == [501]
    assert len(stored_lines) == 1
    assert stored_lines[0].qty == Decimal("10")
```

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integration/test_post_submission_tracking_job.py -q` — expected FAIL (`ModuleNotFoundError`).

- [ ] **Step 3: Implement**

In `packages/tender/etender_connector.py`, add near the other two `_live` functions (after `fetch_procurement_plan_page_live`):

```python
async def fetch_event_details_live(
    conn: AsyncConnection, validator: EgressValidator, *, event_id: int
) -> tuple[bytes, dict[str, Any]]:
    url = f"https://etender.gov.az/api/events/{event_id}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"eTender event details returned HTTP {status} for {url!r}")
    return body, json.loads(body)


async def fetch_bom_lines_page_live(
    conn: AsyncConnection, validator: EgressValidator, *, event_id: int, page_number: int
) -> tuple[bytes, dict[str, Any]]:
    params = {"PageSize": 100, "PageNumber": page_number}
    url = f"https://etender.gov.az/api/events/{event_id}/bomLines?{urlencode(params)}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"eTender BOM lines page returned HTTP {status} for {url!r}")
    return body, json.loads(body)
```

Create `packages/tender/post_submission_tracking_job.py`:

```python
"""Post-submission tracking (Task 4.B, TENDER_INTELLIGENCE_SPEC.md §7.2,
P317): re-checks one already-decided (bid/conditional_bid) tender's
event_details on eTender, and -- only if something changed -- re-walks its
BOM-lines pages to find which specific lines changed. The event_details
re-check reuses the EXISTING immutable versioning (ingest_event_details
already creates a new tender_versions row per call, never an overwrite).
The BOM-lines re-walk is diffed IN MEMORY ONLY against the already-stored
boq_lines rows -- it never calls store_boq_lines again for this event_id,
because boq_lines has no schema support for a second generation of the same
source_line_id (UNIQUE (source, event_id, source_line_id), no upsert)."""

from __future__ import annotations

import json
from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception

from .boq_line_diff import diff_boq_lines
from .boq_line_model import build_boq_lines
from .boq_lines_store import list_boq_lines_by_event
from .change_tracking_store import store_boq_line_recalc_flag, store_tender_change_event, upsert_watch_state
from .etender_connector import ingest_event_details
from .normalized import get_current_tender_version_id, get_event_id_for_tender
from .schema_drift import SchemaDriftDetected
from .tender_change_detection import classify_change_type, diff_normalized_fields

JOB_TYPE = "tender_change_check"

FetchEventDetails = Callable[[int], Awaitable[tuple[bytes, dict[str, Any]]]]
FetchBomPage = Callable[[int, int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def check_tender_for_changes(
    conn: AsyncConnection,
    *,
    tender_id: int,
    fetch_event_details: FetchEventDetails,
    fetch_bom_page: FetchBomPage,
    correlation_id: str,
    observed_at: str,
) -> dict[str, Any]:
    event_id = await get_event_id_for_tender(conn, tender_id=tender_id)
    if event_id is None:
        raise ValueError(f"tender {tender_id} has no resolvable event id -- cannot track for changes")

    previous_version_id = await get_current_tender_version_id(conn, tender_id=tender_id)
    previous_fields: dict[str, Any] = {}
    if previous_version_id is not None:
        row = (
            await conn.execute(
                text("SELECT normalized_fields FROM tender_versions WHERE id = :id"),
                {"id": previous_version_id},
            )
        ).first()
        if row is not None:
            value = row[0]
            previous_fields = json.loads(value) if isinstance(value, str) else value

    raw_body, payload = await fetch_event_details(event_id)

    try:
        new_version = await ingest_event_details(conn, raw_body=raw_body, payload=payload, correlation_id=correlation_id)
    except SchemaDriftDetected as drift_exc:
        await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason=str(drift_exc),
            correlation_id=correlation_id,
            raw_ref=drift_exc.raw_snapshot_id,
            contract_name=drift_exc.contract_name,
        )
        await upsert_watch_state(conn, tender_id=tender_id, checked_at=observed_at)
        return {"change_detected": False, "change_type": None, "flagged_line_count": 0}

    changes = diff_normalized_fields(previous_fields, new_version.normalized_fields)
    flagged_line_count = 0
    change_type: str | None = None

    if changes:
        change_type = classify_change_type(changes)
        change_event_id = await store_tender_change_event(
            conn,
            tender_id=tender_id,
            change_type=change_type,
            changed_fields=changes,
            detected_at=observed_at,
            raw_snapshot_id=new_version.raw_snapshot_id,
        )

        old_lines = await list_boq_lines_by_event(conn, source="etender", event_id=event_id)
        new_lines = []
        page_number = 1
        while True:
            page_raw_body, page_payload = await fetch_bom_page(event_id, page_number)
            new_lines.extend(build_boq_lines(page_number=page_number, items=page_payload["items"]))
            total_pages = page_payload.get("totalPages")
            if total_pages is None or page_number >= total_pages:
                break
            page_number += 1

        changed_line_ids = diff_boq_lines(old_lines, new_lines)
        for source_line_id in changed_line_ids:
            await store_boq_line_recalc_flag(
                conn,
                tender_id=tender_id,
                boqline_source_line_id=source_line_id,
                change_event_id=change_event_id,
                flagged_at=observed_at,
            )
        flagged_line_count = len(changed_line_ids)

    await upsert_watch_state(conn, tender_id=tender_id, checked_at=observed_at)

    return {"change_detected": bool(changes), "change_type": change_type, "flagged_line_count": flagged_line_count}
```

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/integration/test_post_submission_tracking_job.py -q` — expected PASS.
Run: `python -m ruff check packages/tender/post_submission_tracking_job.py` — must be clean (no `__import__` calls, no unused imports).

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py packages/tender/post_submission_tracking_job.py tests/integration/test_post_submission_tracking_job.py
git commit -m "feat(tender): live-fetch wrappers + post-submission tracking job (task 4.B)"
```

---

### Task 6: Worker wiring, read API, and recorded gaps

**Files:**
- Modify: `apps/worker/main.py` (job-type dispatch registry, due-tender enqueue loop)
- Modify: `apps/api_tender/routers/decision.py` (one new GET route) — or create `apps/api_tender/routers/tender_tracking.py` and wire it into `apps/api_tender/main.py`'s router registration (check `apps/api_tender/main.py` for how `decision.router` is currently included, and follow the identical pattern for the new router)
- Modify: `docs/decisions/OPEN-QUESTIONS.md`, `docs/reports/WORKLOG.md`
- Test: `tests/integration/test_worker_dispatch.py` (new), `tests/integration/test_tender_tracking_api.py` (new)

**Interfaces:**
- Consumes: `JOB_TYPE` from `post_submission_tracking_job.py` (Task 5), `list_tenders_with_active_bid_decision` (Task 4), `list_tenders_due_for_check` (Task 4), `list_unresolved_recalc_flags` (Task 3).
- Produces: `GET /tenders/{tender_id}/recalc-flags` (permission `decision.recalc_flags.read` — add this permission the same way `decision.bid_readiness.read` etc. were seeded/checked in tests) returning the unresolved flags for that tender.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/test_worker_dispatch.py
from __future__ import annotations

import apps.worker.main as worker_main
from packages.platform.jobs import JobIdentity, JobStore
from packages.tender.post_submission_tracking_job import JOB_TYPE as TENDER_CHECK_JOB_TYPE


async def test_worker_dispatches_a_tender_change_check_job(engine, monkeypatch):
    calls = []

    async def fake_check_tender_for_changes(conn, *, tender_id, fetch_event_details, fetch_bom_page, correlation_id, observed_at):
        calls.append(tender_id)
        return {"change_detected": False, "change_type": None, "flagged_line_count": 0}

    # apps/worker/main.py imports the job module as `tender_change_check_job`
    # -- patch the attribute on that module object so the dispatch code
    # (which calls `tender_change_check_job.check_tender_for_changes(...)`)
    # picks up the stub without needing a real eTender fetch or a real
    # egress validator.
    monkeypatch.setattr(worker_main.tender_change_check_job, "check_tender_for_changes", fake_check_tender_for_changes)

    store = JobStore()
    async with engine.begin() as conn:
        job_id = await store.enqueue(
            conn,
            JobIdentity(
                job_type=TENDER_CHECK_JOB_TYPE,
                params={"tender_id": 4242},
                source="etender",
                range_start=None,
                range_end=None,
                contract_version="etender.event_details",
                correlation_id="test-worker-dispatch-1",
            ),
        )

    claimed = await worker_main.run_once(engine, store, worker_id="test-worker-1")

    assert claimed is True
    assert calls == [4242]

    async with engine.begin() as conn:
        job = await store.get(conn, job_id)
    assert job.status == "completed"
```

```python
# tests/integration/test_tender_tracking_api.py
from __future__ import annotations

# Follow tests/integration/test_decision_api.py's exact fixture pattern
# (tender_app, client, pm_user, user_without_decision_permissions) --
# reuse it, don't reinvent it.


async def test_recalc_flags_requires_auth(client, tender_with_boq):
    response = await client.get(f"/tenders/{tender_with_boq}/recalc-flags")
    assert response.status_code == 401


async def test_recalc_flags_returns_empty_list_when_none_flagged(client, pm_user, tender_with_boq):
    response = await client.get(f"/tenders/{tender_with_boq}/recalc-flags", headers={"X-Dev-User": "pm-1"})
    assert response.status_code == 200
    assert response.json() == []


async def test_recalc_flags_returns_a_flag_after_one_is_stored(client, pm_user, tender_with_boq, engine):
    from packages.tender.change_tracking_store import store_boq_line_recalc_flag, store_tender_change_event
    from packages.tender.tender_change_detection import TenderFieldChange

    async with engine.begin() as conn:
        change_event_id = await store_tender_change_event(
            conn,
            tender_id=tender_with_boq,
            change_type="deadline_shift",
            changed_fields=(TenderFieldChange(field="end_date", old_value=1, new_value=2),),
            detected_at="2026-08-09T12:00:00+00:00",
            raw_snapshot_id=1,
        )
        await store_boq_line_recalc_flag(
            conn,
            tender_id=tender_with_boq,
            boqline_source_line_id=1,
            change_event_id=change_event_id,
            flagged_at="2026-08-09T12:00:00+00:00",
        )

    response = await client.get(f"/tenders/{tender_with_boq}/recalc-flags", headers={"X-Dev-User": "pm-1"})
    assert response.status_code == 200
    body = response.json()
    assert len(body) == 1
    assert body[0]["boqline_source_line_id"] == 1
```
(`raw_snapshot_id=1` above assumes `tender_with_boq`'s fixture already inserted at least one `raw_snapshots` row earlier in the same test transaction/fixture chain — if that FK doesn't resolve, use the `raw_snapshot_id` that `tender_with_boq`'s own fixture setup returns/stores instead of the literal `1`; check `tests/integration/test_decision_api.py`'s `tender_with_boq` fixture for the exact variable name holding it.)

- [ ] **Step 2: Run to verify they fail**

Run: `python -m pytest tests/integration/test_worker_dispatch.py tests/integration/test_tender_tracking_api.py -q` — expected FAIL.

- [ ] **Step 3: Implement**

In `apps/worker/main.py`, replace the single-type check in `_process_claimed_job` with a small registry. Replace:
```python
    try:
        if job.job_type != example_job.JOB_TYPE:
            raise ValueError(f"unknown job_type: {job.job_type}")

        done = job.checkpoint.get("done", False)
        while not done:
            async with engine.begin() as conn:
                current = await store.get(conn, job.id)
                assert current is not None, f"job {job.id} vanished mid-processing (jobs are never deleted)"
                checkpoint = await example_job.process_page(conn, current)
                await store.checkpoint(conn, job.id, worker_id, checkpoint)
            done = checkpoint["done"]
```
with:
```python
    try:
        if job.job_type == example_job.JOB_TYPE:
            done = job.checkpoint.get("done", False)
            while not done:
                async with engine.begin() as conn:
                    current = await store.get(conn, job.id)
                    assert current is not None, f"job {job.id} vanished mid-processing (jobs are never deleted)"
                    checkpoint = await example_job.process_page(conn, current)
                    await store.checkpoint(conn, job.id, worker_id, checkpoint)
                done = checkpoint["done"]
        elif job.job_type == tender_change_check_job.JOB_TYPE:
            async with engine.begin() as conn:
                current = await store.get(conn, job.id)
                assert current is not None, f"job {job.id} vanished mid-processing (jobs are never deleted)"
                # get_egress_validator() is called lazily INSIDE each lambda,
                # not eagerly here -- so a test that monkeypatches
                # check_tender_for_changes itself (never invoking these
                # lambdas) never needs a real validator/settings/network.
                await tender_change_check_job.check_tender_for_changes(
                    conn,
                    tender_id=current.params["tender_id"],
                    fetch_event_details=lambda event_id: etender_connector.fetch_event_details_live(
                        conn, get_egress_validator(), event_id=event_id
                    ),
                    fetch_bom_page=lambda event_id, page_number: etender_connector.fetch_bom_lines_page_live(
                        conn, get_egress_validator(), event_id=event_id, page_number=page_number
                    ),
                    correlation_id=current.correlation_id,
                    observed_at=_now_iso(),
                )
                await store.checkpoint(conn, job.id, worker_id, {"done": True})
        else:
            raise ValueError(f"unknown job_type: {job.job_type}")
```

Add the needed imports at the top of `apps/worker/main.py`:
```python
from packages.tender import etender_connector
from packages.tender import post_submission_tracking_job as tender_change_check_job
```
Check `packages/platform/egress/validator.py` for the exact constructor/factory this codebase already uses to build an `EgressValidator` in a live context (grep other call sites, e.g. anywhere `EgressValidator(` is instantiated for real use outside tests) and use that exact pattern to write a small `get_egress_validator() -> EgressValidator` function in `apps/worker/main.py` — do not invent a new construction path if one already exists. Add a small `_now_iso() -> str` helper (`datetime.now(UTC).isoformat()`) near the top of the file if one doesn't already exist there.

Add a due-tender enqueue step to `run_forever`, right before the existing `while True:` loop body's `claimed = await run_once(...)` line — call a new function once per outer loop iteration (not on every single job claim) so it doesn't spam the DB:

```python
async def enqueue_due_tender_checks(engine: AsyncEngine) -> int:
    async with engine.begin() as conn:
        tracked = await list_tenders_with_active_bid_decision(conn)
        due = await list_tenders_due_for_check(
            conn, tender_ids=tracked, now=_now_iso(), interval_hours=TENDER_WATCH_POLL_INTERVAL_HOURS
        )
        store = JobStore()
        for tender_id in due:
            await store.enqueue(
                conn,
                JobIdentity(
                    job_type=tender_change_check_job.JOB_TYPE,
                    params={"tender_id": tender_id},
                    source="etender",
                    range_start=None,
                    range_end=None,
                    contract_version="etender.event_details",
                    correlation_id=f"tender-watch-{tender_id}",
                ),
            )
    return len(due)
```
with `TENDER_WATCH_POLL_INTERVAL_HOURS = 6  # owner decision, 2026-08-09 -- no source document supplies this number` as a module constant, and `from packages.decision.decision_store import list_tenders_with_active_bid_decision` / `from packages.tender.change_tracking_store import list_tenders_due_for_check` / `from packages.platform.jobs import JobIdentity` added to imports. Call `await enqueue_due_tender_checks(engine)` once at the top of each `while True:` iteration in `run_forever` (this makes the check cheap-but-frequent against `tender_watch_state`'s own timestamp gate, so calling it every poll cycle is safe and idempotent — it will simply enqueue nothing on cycles where nothing is due).

For the read route, check `apps/api_tender/main.py` for exactly how `decision.router` is registered, then add a new route to `apps/api_tender/routers/decision.py` (same file, same `router` object, so it shares the `/tenders/{tender_id}` prefix already declared there):

```python
class RecalcFlagResponse(BaseModel):
    id: int
    boqline_source_line_id: int
    change_event_id: int
    flagged_at: datetime


@router.get("/recalc-flags", response_model=list[RecalcFlagResponse])
async def get_recalc_flags(
    tender_id: int,
    conn: AsyncConnection = Depends(get_connection),
    identity: Identity = Depends(require_permission("decision.recalc_flags.read", get_current_identity)),
) -> list[RecalcFlagResponse]:
    flags = await list_unresolved_recalc_flags(conn, tender_id=tender_id)
    return [
        RecalcFlagResponse(
            id=f["id"],
            boqline_source_line_id=f["boqline_source_line_id"],
            change_event_id=f["change_event_id"],
            flagged_at=f["flagged_at"],
        )
        for f in flags
    ]
```
Add `from packages.tender.change_tracking_store import list_unresolved_recalc_flags` to `decision.py`'s imports.

In `docs/decisions/OPEN-QUESTIONS.md`, append a new dated entry recording: (1) Q&A/clarifications tracking is NOT built (no captured eTender endpoint for it — needs a discovery session like the one that found the events-list query contract in task 1.A); (2) nothing yet resolves a `boq_line_recalc_flags` row's `resolved_at` — it stays flagged forever until some future process (presumably re-running `GET /bid-readiness-candidate`) explicitly clears it, which this task does not build.

In `docs/reports/WORKLOG.md`, append an entry for this task summarizing what was built, mirroring the existing entries' style and level of detail.

- [ ] **Step 4: Run to verify they pass**

Run: `python -m pytest tests/ -q -m "not live_network"` — all pass, including the new files.
Run: `python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py`.

- [ ] **Step 5: Commit**

```bash
git add apps/worker/main.py apps/api_tender/routers/decision.py docs/decisions/OPEN-QUESTIONS.md docs/reports/WORKLOG.md tests/integration/test_worker_dispatch.py tests/integration/test_tender_tracking_api.py
git commit -m "feat(worker,api-tender): wire post-submission tracking job into the real worker dispatch, expose recalc-flags read route (task 4.B)"
```
