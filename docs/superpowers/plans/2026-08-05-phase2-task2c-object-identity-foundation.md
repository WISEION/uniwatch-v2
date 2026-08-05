# Phase 2, Task 2.C — Object identity foundation (region canonicalization + signal accumulation) — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the minimal, real piece of `TENDER_INTELLIGENCE_SPEC.md` §5.3's "граф объектов"
(object graph) that task 2.B's two signal sources can actually support today: canonicalizing an
Azerbaijan rayon/region name so multiple signals about the *same* real region are recognized as the
same object, and a query primitive to list a region's accumulated signals ("накопленные сигналы").
This is explicitly **not** the full composite-trigger engine (weak/medium/strong tiers, §5.3) — that
needs a second independent signal *category* sharing real objects with an existing one, which this
plan's own reconnaissance shows does not exist yet between the two sources built so far.

**Why this scope, not composite triggers yet (record the investigation, don't skip it silently):**
- **Checked, real, negative result:** all 147 real design/TEO-tender records (both frozen fixture pages
  plus 13 more pages fetched during this investigation, not yet frozen as fixtures) were fuzzy-matched
  against all 32 real World Bank donor-pipeline agency names (`impagency`/`borrower` across all 79 real
  AZ projects). Zero token overlap. The two real agency-name matches found by direct search
  (`AZƏRSU`, `AZƏRENERJİ` both have current real eTender activity) are tied to World Bank loans
  **closed** in 1995/2005/2007 — pairing a decades-closed loan with a 2026 tender is not a real forecast
  signal, just coincidental activity by a large utility that always has *something* open. Of the 79 real
  AZ World Bank records, only **one** (`P505208`, `Pipeline` status) is actually fresh, and it has no
  named agency yet (pre-approval) to anchor against anything.
- **A more promising real pattern exists, but needs a second category, not more of the same one:**
  eTender's own design-tender data already names specific rayons via their executive authorities'
  buyer names (e.g. `ZAQATALA RAYONU İCRA HAKİMİYYƏTİ` appears on **4** of the 10 real tenders in the
  frozen page 1 fixture) — exact, simple string matching, unlike cross-language agency-name fuzzy
  matching. A genuine composite signal (e.g. a regional budget line or decree naming the same rayon,
  landing within its own signal's TTL window, intersecting with a design-tender signal from that
  rayon's executive authority) is the real target — but building that second category
  (`TENDER_INTELLIGENCE_SPEC.md` §5.2's decrees/budgets, via president.az/e-qanun.az) hit a real recon
  wall earlier (a plain `WebFetch` returned no usable page structure) and is **not resolved by this
  plan** — it needs a different recon method (a live browser trace, the same technique that cracked
  eTender's own list-endpoint contract in the 2026-08-04 follow-up session), attempted separately.
- Given that, the highest-value buildable-today step is the **object-identity primitive itself** —
  proven against the one real object (a rayon) that already has multiple independent *observations*
  within the one source that has it (eTender), which is real progress on "накопленные сигналы" even
  before a second category exists to intersect with it.

**Architecture:** `packages/tender/az_region_identity.py` gets a pure `canonicalize_region()` function,
built from the real rayon/city name tokens actually observed in the two already-frozen design-tender
fixture pages (`Zaqatala`, `Siyəzən`, `Lerik`, `Naxçıvan`) — not a hand-typed list of all ~66 Azerbaijan
administrative regions, which would risk transcription errors for regions never actually observed.
`design_tender_signal.py`'s `build_design_tender_signal()` is updated to populate the *already-existing*
`object_region` field (currently always `None` for this signal type) using this function, instead of
adding a new column. `signals_store.py` gets `list_signals_by_object` for the accumulation query.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async — no new dependencies, no schema migration (reuses
the existing `signals.object_region` column, currently unpopulated for this signal type).

## Global Constraints

- No fabricated gazetteer. `canonicalize_region()`'s known-region list is built *only* from region
  names actually present in `fixtures/tender-snapshots/etender/design_tender_search_page{1,2}.raw.json`
  — real buyer-organization text this task can point to, not a general Azerbaijan rayon list typed from
  memory (which risks getting an unobserved region's spelling wrong and silently mis-normalizing it).
  Extending the list to more regions is real, easy future work once more pages are frozen, not attempted
  speculatively here.
- `object_region` already exists on `signals` (added in the World Bank slice's migration,
  `migrations/0008_signals.sql`) and is already a field on `Signal`/`build_design_tender_signal()` —
  this plan populates it, it does not add a column or change the `Signal` dataclass's shape.
- This plan does **not** build composite/intersection-trigger detection (§5.3's weak/medium/strong
  tiers) — that is explicitly deferred pending a second real, overlapping signal category. Do not scope
  creep into building a "forecast" output here.
- This plan does **not** attempt president.az/e-qanun.az reconnaissance — that failed once already
  (plain `WebFetch`, no usable structure returned) and needs a different method (live browser trace),
  which is a separate investigation, not part of this plan's tasks.

---

## Task 1: `az_region_identity.py` — region canonicalization from real observed data

**Files:**
- Create: `packages/tender/az_region_identity.py`
- Test: `tests/unit/test_az_region_identity.py`

**Interfaces:**
- Produces: `canonicalize_region(text: str) -> str | None` — pure function, no DB, no network.

- [ ] **Step 1: Write the failing test**

```python
from packages.tender.az_region_identity import canonicalize_region


def test_canonicalizes_real_rayon_executive_authority_names():
    # Real buyerOrganizationName values, fixtures/tender-snapshots/etender/design_tender_search_page1.raw.json.
    assert canonicalize_region("ZAQATALA RAYONU İCRA HAKİMİYYƏTİ.") == "Zaqatala"
    assert canonicalize_region("SİYƏZƏN RAYON İCRA HAKİMİYYƏTİ") == "Siyəzən"
    assert canonicalize_region("LERİK RAYON İCRA HAKİMİYYƏTİ") == "Lerik"
    assert canonicalize_region("NAXÇIVAN ŞƏHƏR İCRA HAKİMİYYƏTİ") == "Naxçıvan"


def test_returns_none_for_unrecognized_or_non_regional_buyers():
    # Real buyerOrganizationName values with no recognizable region token.
    assert canonicalize_region('"TİKİLMƏKDƏ OLAN OBYEKTLƏRİN MÜDİRİYYƏTİ" PUBLİK HÜQUQİ ŞƏXSİ') is None
    assert canonicalize_region("AZƏRBAYCAN RESPUBLİKASI DÖVLƏT NEFT FONDU") is None
```

Save as `tests/unit/test_az_region_identity.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_az_region_identity.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.az_region_identity'`.

- [ ] **Step 3: Write `az_region_identity.py`**

```python
"""Region-name canonicalization (TENDER_INTELLIGENCE_SPEC.md §5.3's
"граф объектов" -- object graph -- foundation, not the full graph). Pure
string matching, built only from region names actually observed in real
captured eTender buyer names
(fixtures/tender-snapshots/etender/design_tender_search_page{1,2}.raw.json)
-- not a general list of Azerbaijan's ~66 rayons typed from memory, which
would risk an unobserved region's spelling being wrong and silently
mis-normalizing text that happens to contain it.

Extending _KNOWN_REGIONS to more regions is real, easy future work once
more real buyer names are captured -- not attempted speculatively here."""

from __future__ import annotations

# Canonical name -> the token(s) that identify it inside a real
# buyerOrganizationName string (uppercase, as eTender returns them).
_KNOWN_REGIONS: dict[str, tuple[str, ...]] = {
    "Zaqatala": ("ZAQATALA",),
    "Siyəzən": ("SİYƏZƏN",),
    "Lerik": ("LERİK",),
    "Naxçıvan": ("NAXÇIVAN",),
}


def canonicalize_region(text: str) -> str | None:
    upper = text.upper()
    for canonical, tokens in _KNOWN_REGIONS.items():
        if any(token in upper for token in tokens):
            return canonical
    return None
```

Save as `packages/tender/az_region_identity.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_az_region_identity.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/az_region_identity.py tests/unit/test_az_region_identity.py
git commit -m "feat(tender): region canonicalization from real observed eTender buyer names"
```

---

## Task 2: Populate `object_region` on design-tender signals

**Files:**
- Modify: `packages/tender/design_tender_signal.py`
- Modify: `tests/unit/test_design_tender_signal.py`

**Interfaces:**
- Consumes: `canonicalize_region` (Task 1).
- Produces: `build_design_tender_signal()`'s `object_region` is no longer unconditionally `None` — it is
  `canonicalize_region(item["buyerOrganizationName"])`, which is `None` exactly when no known region
  token matches (still honest — not every real buyer name names a region this task has observed).

- [ ] **Step 1: Update the existing tests that assert `object_region is None`**

In `tests/unit/test_design_tender_signal.py`, `test_build_design_tender_signal_from_real_open_tender`
uses buyer `"AZƏRSU ASC"` (no region token) and currently asserts `signal.object_region is None` —
this remains correct and unchanged (AzərSu is a national utility, not a rayon executive authority).

Add a new test:
```python
def test_build_design_tender_signal_canonicalizes_real_region():
    item = {
        "eventId": 356430,
        "eventName": "Nizami küçəsində yerləşən bağda abadlıq işləri ilə əlaqədar layihə smeta sənədlərinin hazırlanması",
        "buyerOrganizationName": "ZAQATALA RAYONU İCRA HAKİMİYYƏTİ.",
        "publishDate": 1735689600000,
        "awardedParticipantName": None,
        "documentViewType": 1,
    }
    signal = build_design_tender_signal(
        item, raw_snapshot_id=101, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-design-3"
    )
    assert signal.object_region == "Zaqatala"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_design_tender_signal.py -v`
Expected: the new test FAILs (`assert None == "Zaqatala"`); all pre-existing tests still PASS.

- [ ] **Step 3: Update `build_design_tender_signal`**

In `packages/tender/design_tender_signal.py`, add the import and change the `object_region=None,` line:

```python
from .az_region_identity import canonicalize_region
```

```python
object_region = (canonicalize_region(item.get("buyerOrganizationName", "")),)
```

Update the docstring comment above that line (currently says "eTender's events-list item has no
structured region ... field" as the reason for `None`) to reflect that a *known* region token is now
extracted from the buyer name when present, and `None` remains honest for buyers that don't name one of
the regions observed so far (see `az_region_identity.py`'s own docstring for why the list isn't
exhaustive).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_design_tender_signal.py -v`
Expected: all PASS, including the new test.

- [ ] **Step 5: Re-run the integration tests that ingest real fixtures end-to-end**

Run: `python -m pytest tests/integration/test_design_tender_ingestion.py tests/integration/test_design_tender_job.py -v`
Expected: all PASS (these tests check event ids / counts, not `object_region`, so they are unaffected
— but running them confirms nothing broke downstream).

- [ ] **Step 6: Commit**

```bash
git add packages/tender/design_tender_signal.py tests/unit/test_design_tender_signal.py
git commit -m "feat(tender): populate object_region on design-tender signals from real buyer names"
```

---

## Task 3: Signal accumulation query — `list_signals_by_object_region`

**Files:**
- Modify: `packages/tender/signals_store.py`
- Test: `tests/integration/test_signal_accumulation.py`

**Interfaces:**
- Produces: `async def list_signals_by_object_region(conn: AsyncConnection, *, object_region: str) ->
  list[dict[str, Any]]` — the "накопленные сигналы" (accumulated signals) primitive
  `TENDER_INTELLIGENCE_SPEC.md` §5.3 needs, scoped to one real object regardless of `signal_type`
  (unlike `list_signals`, which filters by type).

- [ ] **Step 1: Write the failing test (real accumulation on a real object)**

```python
import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page
from packages.tender.signals_store import list_signals_by_object_region

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"

QUERY_PARAMS = {
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


async def test_zaqatala_accumulates_all_four_real_signals(engine):
    raw_body = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=QUERY_PARAMS,
            correlation_id="corr-accum-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        rows = await list_signals_by_object_region(conn, object_region="Zaqatala")
        # Real fact: 4 of the 10 tenders on this page are all from Zaqatala Rayon İcra Hakimiyyəti
        # (events 356430, 356426, 356418, 356406) -- see MANIFEST.md.
        assert len(rows) == 4
        assert {row["value"]["event_id"] for row in rows} == {356430, 356426, 356418, 356406}
```

Save as `tests/integration/test_signal_accumulation.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_signal_accumulation.py -v`
Expected: FAIL with `ImportError: cannot import name 'list_signals_by_object_region'`.

- [ ] **Step 3: Add `list_signals_by_object_region` to `signals_store.py`**

Append (reuse the existing `list_signals`'s row-to-dict conversion pattern — read the file first to
match its exact `.mappings().all()` / JSON-decoding style):

```python
async def list_signals_by_object_region(conn: AsyncConnection, *, object_region: str) -> list[dict[str, Any]]:
    rows = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, signal_type, source, raw_snapshot_id, value, observed_at, ttl_class,
                           confidence, object_customer, object_region, object_project_type, correlation_id
                    FROM signals WHERE object_region = :object_region ORDER BY observed_at
                    """
                ),
                {"object_region": object_region},
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_signal_accumulation.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/signals_store.py tests/integration/test_signal_accumulation.py
git commit -m "feat(tender): signal accumulation query by object_region"
```

---

## Task 4: WORKLOG and Open Questions

**Files:**
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

- [ ] **Step 1: Run the full gate**

Run:
```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```
Expected: 0 failures, 0 issues, PASS.

- [ ] **Step 2: WORKLOG entry**

State plainly: (a) this is a *partial* foundation for task 2.C (object identity + accumulation for
region only), not the composite-trigger engine; (b) the World Bank↔eTender agency-matching path was
investigated with real data and found not viable now (zero fuzzy overlap across 147×32 real records;
the two name matches found are tied to WB loans closed 19-31 years ago); (c) a genuine second signal
category sharing real objects with the design-tender source (decrees/budgets naming the same rayons)
remains the real unlock for actual composite triggers, and president.az/e-qanun.az reconnaissance
remains open — a plain `WebFetch` returned no usable structure, a live-browser-trace attempt (the
method that worked for eTender's own list endpoint) has not been tried.

- [ ] **Step 3: Open Questions entry**

Record: `_KNOWN_REGIONS` in `az_region_identity.py` covers exactly 4 real observed regions
(Zaqatala/Siyəzən/Lerik/Naxçıvan) — every other real Azerbaijan rayon/city that might appear in a
future buyer name will canonicalize to `None` until it is actually observed and added; this is a
real, honest recall gap, not a hidden one.

- [ ] **Step 4: Commit**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(tender): close out object-identity foundation, record decree recon as still open"
```

---

## Self-review notes

- **Spec coverage:** this is a deliberately partial slice of `TENDER_INTELLIGENCE_SPEC.md` §5.3 (object
  identity + accumulation), not the composite-trigger engine — the plan's own Global Constraints say so
  explicitly, and Task 4 records why, backed by the real WB↔eTender overlap check performed before
  writing this plan (zero overlap across all real records checked).
- **No placeholders:** every example region/event id traces to the two already-frozen, real fixture
  pages. The gazetteer's real limitation (4 regions only) is stated, not hidden.
