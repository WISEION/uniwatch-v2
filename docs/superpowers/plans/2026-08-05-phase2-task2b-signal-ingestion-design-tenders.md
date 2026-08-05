# Phase 2, Task 2.B — Signal ingestion (design/TEO-tender slice, second source) — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a **second** signal source for `TENDER_INTELLIGENCE_SPEC.md` §5.2 (task 2.B), in a
genuinely different category from the first (World Bank donor pipeline, see
`docs/superpowers/plans/2026-08-05-phase2-task2b-signal-ingestion-worldbank.md`): design/TEO
(feasibility-study) tenders — `TENDER_INTELLIGENCE_SPEC.md` §5.2's "тендеры на ТЭО/проектирование"
category. Unlike the World Bank slice, this source needs **no new external host, no new egress trust,
no new raw-ingestion contract** — it is a derived-signal layer over eTender events-list pages that
task 1.A's `ingest_events_list_page()` already knows how to fetch/validate/normalize. This proves the
`Signal` mechanism generalizes to in-house-derived signals, not just newly-onboarded external ones.

**Architecture:** `packages/tender/design_tender_signal.py` gets a pure keyword classifier
(`classify_design_tender`) and a builder (`build_design_tender_signal`), both grounded in real eTender
search results captured during this task's reconnaissance (2026-08-05). A new
`ingest_design_tender_signals_page()` in `etender_connector.py` calls the *existing*
`ingest_events_list_page()` for raw/drift/normalize (reused unchanged in mechanism, only its identity
model is widened — see Task 2), then classifies each item on that already-ingested page and stores a
`Signal` per match. A resumable pagination job (`design_tender_job.py`, mirrors `bom_lines_job.py`)
walks eTender's own server-side `Keyword=layihə` search results — 147 real candidate tenders across 15
real pages at `PageSize=10`, not a full unfiltered corpus scan.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async + `asyncpg`, PostgreSQL (via `testcontainers` in
tests) — no new dependencies, no new external host.

## Global Constraints

- No fabricated data. All example values below (`eventId 356515`, the two false-positive tender names,
  the `layihələmdirilməsi` typo variant, `totalItems: 147`, `totalPages: 15`) come from a real, live
  search against `https://etender.gov.az/api/events` with `Keyword=layihə&EventStatus=1&IsArchived=false`
  made 2026-08-05 during this task's reconnaissance. Task 1 re-captures and freezes two of those pages
  as fixtures.
- **The classifier is keyword-based and has a known, real false-positive/false-negative profile — this
  is stated honestly, not hidden.** `layihə` alone means "project" in Azerbaijani generically (matches
  non-design tenders like office-space rental tied to "layihələrin idarə olunması" = "management of
  projects", or "layihələrin təşkili" = "organizing of projects") as well as "design" in the
  construction-industry sense (`layihə-smeta` = "design + estimate documents"). Azerbaijani morphology
  gives a precise fix beyond a bare substring match: the *verb* stem meaning "to design" is
  `layihələn-`/`layihələm-` (the latter a real observed typo for the former) — 9 characters, ending in
  `n`/`m` — while the *plural noun* "projects" is `layihələr-` — same first 8 characters (`layihələ`)
  but a 9th character of `r`. The classifier in Task 3 requires the full 9-character verb stems
  (`layihələn`/`layihələm`) or the `layihə-smeta`/`layihə smeta`/`layihəsmeta` noun-phrase variants, not
  the bare 8-character `layihələ` prefix (which would incorrectly match the plural noun too) and not the
  bare word `layihə`. This mirrors task 2.A's honest keyword-classifier precedent
  (`docs/decisions/OPEN-QUESTIONS.md`, "preliminaries/provisional-sum keywords are English-only") — a
  real, bounded recall/precision tradeoff, not a hidden gap.
- **Object binding stays honest about what eTender's events-list resource actually provides.**
  `object_customer` = `buyerOrganizationName` (a real, always-present field). `object_region` and
  `object_project_type` are `None` for this connector — the events-list item has no structured region
  or project-category field; both are only present as free text buried in `eventName` (e.g. "Qəbələ
  şəhərində", "yolların əsaslı təmiri"). Extracting either would need real gazetteer/NER work against a
  real list of Azerbaijan administrative regions, or a real category-keyword taxonomy — genuine,
  separate future work, not attempted here as a guess (same discipline as the World Bank slice leaving
  `object_region` at country-granularity rather than guessing finer).
- **This task closes a real, previously-flagged gap: filter-aware identity for the events-list
  resource.** `docs/decisions/OPEN-QUESTIONS.md`/`tests/test_regression_registry.py` (task 1.E) recorded
  "events-list resumable pagination (contract exists, full implementation with filters — if needed in
  Phase 2)" as explicitly deferred. It is needed now: this task pages through a *filtered* search
  (`Keyword=layihə`), and `EVENTS_LIST_PAGE_CONTRACT.identity_query_keys` currently only tracks
  `PageNumber` — a filtered page 1 and an unfiltered page 1 would collide under the same identity_key
  today. Task 2 fixes this by widening identity to the full real query-parameter set discovered in the
  2026-08-04 follow-up session (`fixtures/tender-snapshots/etender/MANIFEST.md`).
- `ingest_events_list_page()`'s signature changes (adds a required `query_params` argument) — both
  existing call sites (`tests/integration/test_etender_connector.py`,
  `tests/integration/test_traceability.py`) are updated in Task 2, not left broken.
- No new migration. `signals` (from the World Bank slice, `migrations/0008_signals.sql`) is reused
  as-is — this is exactly the point of that table being source-agnostic.
- No new egress trust registration — `etender.gov.az` is already used in the existing SSRF suite
  (`tests/security/test_ssrf_suite.py`'s P304 test registers it test-scoped, same pattern this task's
  live-fetch test reuses).
- Fixture location: `fixtures/tender-snapshots/etender/` (same directory as the existing eTender
  fixtures — this is still the eTender source, just a different query).

---

## Task 1: Real fixture capture — design/TEO-tender search results

**Files:**
- Create: `fixtures/tender-snapshots/etender/design_tender_search_page1.raw.json`
- Create: `fixtures/tender-snapshots/etender/design_tender_search_page2.raw.json`
- Modify: `fixtures/tender-snapshots/etender/MANIFEST.md`

**Interfaces:**
- Produces: two real, frozen JSON response bodies for the `Keyword=layihə` search, used by every later
  task's tests.

- [ ] **Step 1: Capture page 1 live**

Run:
```bash
curl -s "https://etender.gov.az/api/events?EventType=&PageSize=10&PageNumber=1&EventStatus=1&Keyword=layih%C9%99&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false" \
  -o fixtures/tender-snapshots/etender/design_tender_search_page1.raw.json
```

Expected shape (verified live 2026-08-05): `totalItems: 147`, `totalPages: 15`, `currentPage: 1`,
`itemsInPage: 10`, 10 real event ids including `356515` ("Ceyranbatan-Abşeron-Balaxanı-Ramana-Zirə-
Pirallahı magistral su kəməri ... layihə-smeta sənədlərinin hazırlanması") and `356386` ("Layihə-smeta
sənədlərinin hazırlanması xidmətlərinin satınalınması"). Every `awardedParticipantName` on this page is
`null` (all open tenders under `EventStatus=1`).

- [ ] **Step 2: Capture page 2 live**

Run:
```bash
curl -s "https://etender.gov.az/api/events?EventType=&PageSize=10&PageNumber=2&EventStatus=1&Keyword=layih%C9%99&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false" \
  -o fixtures/tender-snapshots/etender/design_tender_search_page2.raw.json
```

Expected shape: `currentPage: 2`, same `totalItems`/`totalPages`, 10 different real event ids
(356291, 356192, 356143, 356140, 356055, 356048, 356039, 356027, 355972, 355959). This page contains
two known real **false positives** the classifier (Task 3) must correctly reject: event `356291`
("Layihələrin idarə olunması, Fərdi uçota nəzarət və Sosial sığorta departamentləri..." — "management
of projects" departments, an office/archive space rental tender) and event `356027` ("Təşviqat
xarakterli tədbirlərin və layihələrin təşkili ilə bağlı xidmətlərin satın alınması" — "organizing
promotional events and projects") — both use `layihələr-` (plural "projects"), which shares its first
8 characters (`layihələ`) with the design-verb stem `layihələn-`/`layihələm-` but diverges at the 9th
character (`r` vs `n`/`m`) — exactly the distinction Task 3's classifier must get right. Two more items
on this page are true negatives for a different reason: event `356048` ("GPON layihəsi üzrə...") uses
the possessive `layihəsi` ("its project"), not `layihə-smeta`; event `355959` names an institute whose
own name contains "Layihə-Konstruktor" ("Design-Construction..."), not `layihə-smeta`. The remaining 6
items (356192, 356143, 356140, 356055, 355972, and event 356039 "Artezian quyularının
layihələndirilməsi") are true positives.

- [ ] **Step 3: Compute checksums and update the manifest**

Run:
```bash
sha256sum fixtures/tender-snapshots/etender/design_tender_search_page1.raw.json \
          fixtures/tender-snapshots/etender/design_tender_search_page2.raw.json
```

Append to `fixtures/tender-snapshots/etender/MANIFEST.md` (read the file first — add a new table row
block and a new "What these confirm" bullet list, following the existing file's exact style):

```markdown
| `design_tender_search_page1.raw.json` | GET | `https://etender.gov.az/api/events?EventType=&PageSize=10&PageNumber=1&EventStatus=1&Keyword=layih%C9%99&buyerOrganizationName=&documentNumber=&publishDateFrom=&publishDateTo=&AwardedparticipantName=&AwardedparticipantVoen=&DocumentViewType=&IsArchived=false` | 2026-08-05 | 200 | `<paste sha256sum output>` |
| `design_tender_search_page2.raw.json` | GET | same URL with `PageNumber=2` | 2026-08-05 | 200 | `<paste sha256sum output>` |
```

Add a bullet noting: real server-side `Keyword` search for `layihə` returns 147 total matches across 15
pages (`PageSize=10`); every match on page 1/2 has `awardedParticipantName: null` (all open tenders,
`EventStatus=1`); page 2 contains 2 real false positives (events `356291`/`356027`, both using the
plural noun `layihələr-` = "projects", not the design-verb stem `layihələn-`/`layihələm-`) and 2 more
true negatives for other reasons (`356048`'s possessive `layihəsi`, `355959`'s institute name) — a
keyword classifier restricted to the `layihə-smeta`/`layihə smeta`/`layihəsmeta`/`layihələn`/`layihələm`
stems correctly excludes all four (task 2.B design-tender signal slice,
`TENDER_INTELLIGENCE_SPEC.md` §5.2).

- [ ] **Step 4: Commit**

```bash
git add fixtures/tender-snapshots/etender/design_tender_search_page1.raw.json \
        fixtures/tender-snapshots/etender/design_tender_search_page2.raw.json \
        fixtures/tender-snapshots/etender/MANIFEST.md
git commit -m "test(tender): capture real eTender design/TEO-tender search fixtures for task 2.B (design slice)"
```

---

## Task 2: Widen `EVENTS_LIST_PAGE_CONTRACT` to filter-aware identity

**Rationale:** see Global Constraints above — a filtered and unfiltered page 1 must not collide under
the same raw-snapshot identity_key. `identity_query_keys` must include every real query parameter this
resource accepts (the full set discovered in the 2026-08-04 follow-up session), not just the ones this
task happens to vary, because a *different future caller* using a non-empty value for one of the
"currently always empty" params (e.g. `buyerOrganizationName`) would otherwise silently collide with
this task's calls too.

**Files:**
- Modify: `packages/tender/etender_contract.py`
- Modify: `packages/tender/etender_connector.py`
- Modify: `tests/integration/test_etender_connector.py`
- Modify: `tests/integration/test_traceability.py`

**Interfaces:**
- Produces: `EVENTS_LIST_PAGE_CONTRACT.identity_query_keys` now `("EventType", "PageSize", "PageNumber",
  "EventStatus", "Keyword", "buyerOrganizationName", "documentNumber", "publishDateFrom",
  "publishDateTo", "AwardedparticipantName", "AwardedparticipantVoen", "DocumentViewType",
  "IsArchived")`. `ingest_events_list_page(conn, *, raw_body, payload, query_params, correlation_id)` —
  new required `query_params: dict[str, Any]` argument, merged with `{"PageNumber":
  payload["currentPage"]}` to build `identity_params`.

- [ ] **Step 1: Widen the contract's identity keys**

In `packages/tender/etender_contract.py`, change `EVENTS_LIST_PAGE_CONTRACT`'s
`identity_query_keys=("PageNumber",)` to:
```python
identity_query_keys = (
    (
        "EventType",
        "PageSize",
        "PageNumber",
        "EventStatus",
        "Keyword",
        "buyerOrganizationName",
        "documentNumber",
        "publishDateFrom",
        "publishDateTo",
        "AwardedparticipantName",
        "AwardedparticipantVoen",
        "DocumentViewType",
        "IsArchived",
    ),
)
```
Update the contract's existing comment block above it (currently explains why identity was
deliberately just `PageNumber` and defers the real fix to "task 1.B") — replace with a note that task
2.B (design-tender slice) closes this: every real query parameter is now part of identity, so a
filtered and unfiltered page 1 never collide.

- [ ] **Step 2: Update `ingest_events_list_page`'s signature**

In `packages/tender/etender_connector.py`, change:
```python
async def ingest_events_list_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    def normalize_fields(p: dict[str, Any]) -> dict[str, Any]:
        return {
            "current_page": p["currentPage"],
            "total_pages": p["totalPages"],
            "total_items": p["totalItems"],
            "event_ids_in_page": [item["eventId"] for item in p["items"]],
        }

    return await _ingest(
        conn,
        contract=EVENTS_LIST_PAGE_CONTRACT,
        identity_params={"PageNumber": payload["currentPage"]},
        raw_body=raw_body,
```
to:
```python
async def ingest_events_list_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    query_params: dict[str, Any],
    correlation_id: str,
) -> TenderVersion:
    def normalize_fields(p: dict[str, Any]) -> dict[str, Any]:
        return {
            "current_page": p["currentPage"],
            "total_pages": p["totalPages"],
            "total_items": p["totalItems"],
            "event_ids_in_page": [item["eventId"] for item in p["items"]],
        }

    return await _ingest(
        conn,
        contract=EVENTS_LIST_PAGE_CONTRACT,
        identity_params={**query_params, "PageNumber": payload["currentPage"]},
        raw_body=raw_body,
```
(the rest of the function body, after `raw_body=raw_body,`, is unchanged — read the file first to
confirm the exact remaining lines before editing, since this plan only shows the changed prefix).

- [ ] **Step 3: Update the two existing call sites**

`tests/integration/test_etender_connector.py`'s `test_ingest_real_events_list_page_fixture` — add
`query_params={"EventType": "", "PageSize": 6, "EventStatus": 1, "Keyword": "", "buyerOrganizationName": "", "documentNumber": "", "publishDateFrom": "", "publishDateTo": "", "AwardedparticipantName": "", "AwardedparticipantVoen": "", "DocumentViewType": "", "IsArchived": False}`
to the `ingest_events_list_page(...)` call (this is the exact real query that captured
`events_list_page1.raw.json`, per `fixtures/tender-snapshots/etender/MANIFEST.md` — `PageSize=6` there,
not 10).

`tests/integration/test_traceability.py`'s `test_events_list_version_traces_to_its_exact_raw_bytes` —
same `query_params=` addition to its `ingest_events_list_page(...)` call.

- [ ] **Step 4: Run the affected tests**

Run: `python -m pytest tests/integration/test_etender_connector.py tests/integration/test_traceability.py -v`
Expected: all PASS (this is a pure identity-key widening; normalized_fields/checksum assertions are
unaffected).

- [ ] **Step 5: Run the full suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`
Expected: same pass/skip counts as before this task, no new failures.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/etender_contract.py packages/tender/etender_connector.py \
        tests/integration/test_etender_connector.py tests/integration/test_traceability.py
git commit -m "feat(tender): filter-aware identity for events-list pages, closes deferred 1.E gap"
```

---

## Task 3: `design_tender_signal.py` — classifier and signal builder

**Files:**
- Create: `packages/tender/design_tender_signal.py`
- Test: `tests/unit/test_design_tender_signal.py`

**Interfaces:**
- Consumes: nothing new (pure functions, no DB, no network).
- Produces: `classify_design_tender(event_name: str) -> bool` and `build_design_tender_signal(item:
  dict, *, raw_snapshot_id: int, observed_at: str, correlation_id: str) -> Signal` (using the `Signal`
  dataclass from the World Bank slice's `signal_model.py` — reused unchanged, no new dataclass).

- [ ] **Step 1: Write the failing test**

```python
from packages.tender.design_tender_signal import build_design_tender_signal, classify_design_tender


def test_classifies_real_design_estimate_tenders_as_true():
    # Real eventNames, captured 2026-08-05 (fixtures/tender-snapshots/etender/design_tender_search_page1.raw.json).
    assert classify_design_tender(
        "Ceyranbatan-Abşeron-Balaxanı-Ramana-Zirə-Pirallahı magistral su kəməri və trassa boyunca "
        "yerləşən mərkəzi su anbarların tikintisi çərçivəsində layihə-smeta sənədlərinin hazırlanması"
    )
    assert classify_design_tender("Layihə-smeta sənədlərinin hazırlanması xidmətlərinin satınalınması")
    # Real space-separated variant (no hyphen), page 2 of the same search.
    assert classify_design_tender(
        "Nizami küçəsində yerləşən bağda abadlıq işləri ilə əlaqədar layihə smeta sənədlərinin hazırlanması"
    )
    # Real typo variant found in the wild: "layihələmdirilməsi" (should be "layihələndirilməsi").
    assert classify_design_tender(
        "Yanğın əleyhinə sulusöndürmə sisteminin quraşdırılmasının layihələmdirilməsi xidmətlərinin satın alınması"
    )
    # Correct spelling of the same verb stem, a different real tender.
    assert classify_design_tender(
        "Naxçıvan şəhəri, Culfa, Ordubad, Kəngərli və Şərur rayonlarının hər birində bir ədəd olmaqla, "
        "ümumilikdə 5 ədəd körpələr evi-uşaq bağçasının inzibati binalarının tikinti işlərinin "
        "layihələndirilməsi"
    )


def test_rejects_real_false_positives_using_layihe_as_generic_project():
    # Real eventNames, page 2 of the same search (design_tender_search_page2.raw.json, events
    # 356291/356027) -- "layihələr-" here is the PLURAL NOUN "projects" (layihələ + r), sharing its
    # first 8 characters with the design-VERB stem "layihələn-"/"layihələm-" but diverging at the
    # 9th character -- must not be classified as a design/TEO tender.
    assert not classify_design_tender(
        "Layihələrin idarə olunması, Fərdi uçota nəzarət və Sosial sığorta departamentləri, "
        "habelə SÖTMF üçün Ofis sahəsinin və binanın daxilində Arxiv sahəsinin icarəsi "
        "xidmətlərinin satın alınması"
    )
    assert not classify_design_tender(
        "Təşviqat xarakterli tədbirlərin və layihələrin təşkili ilə bağlı xidmətlərin satın alınması"
    )
    # Real true negatives for different reasons -- neither shares the design-verb stem at all.
    assert not classify_design_tender("GPON layihəsi üzrə Bras, Olt ,Ont və digər avadanlıqlarının satınalınması")
    assert not classify_design_tender(
        "FHN TTNDA S.Ə.Dadaşov adına Elmi-Tətqiqat və Layihə-Konstruktor İnşaat Materialları "
        "İnstitutu üçün Daşınma (evakuator) xidmətlərinin satınalınması"
    )


def test_build_design_tender_signal_from_real_open_tender():
    item = {
        "eventId": 356515,
        "eventName": (
            "Ceyranbatan-Abşeron-Balaxanı-Ramana-Zirə-Pirallahı magistral su kəməri layihə-smeta sənədlərinin hazırlanması"
        ),
        "buyerOrganizationName": "AZƏRSU ASC",
        "publishDate": 1735689600000,
        "awardedParticipantName": None,
        "documentViewType": 1,
    }
    signal = build_design_tender_signal(
        item, raw_snapshot_id=99, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-design-1"
    )
    assert signal.signal_type == "design_tender"
    assert signal.source == "etender"
    assert signal.raw_snapshot_id == 99
    assert signal.value["event_id"] == 356515
    assert signal.value["is_awarded"] is False
    assert signal.ttl_class == "design_phase_tender"
    assert signal.confidence == "official_source"
    assert signal.object_customer == "AZƏRSU ASC"
    assert signal.object_region is None
    assert signal.object_project_type is None
```

Save as `tests/unit/test_design_tender_signal.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_design_tender_signal.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.design_tender_signal'`.

- [ ] **Step 3: Write `design_tender_signal.py`**

```python
"""Design/TEO-tender signal detection (TENDER_INTELLIGENCE_SPEC.md §5.2,
P309, second signal source/category after the World Bank donor-pipeline
slice). A derived signal over eTender events-list items eTender's own
existing empirical-contract connector (etender_connector.py) already
fetches and normalizes -- no new external host, no new raw-ingestion
contract.

`classify_design_tender` is a real, bounded keyword classifier, not an
exhaustive NLP model: `layihə` alone means "project" generically in
Azerbaijani (false positives exist, see the rejects-real-false-positives
test) as well as "design" in the construction-industry sense
(`layihə-smeta` = "design + estimate documents", the real, specific term).
Azerbaijani morphology matters here: the *verb* stem for "to design" is
`layihələn-`/`layihələm-` (the latter a real observed typo for the
former), while the *plural noun* "projects" is `layihələr-` -- both share
the first 8 characters (`layihələ`) but diverge at the 9th (`n`/`m` vs
`r`), so the stem list below uses the full 9-character verb forms, not
the shorter, ambiguous 8-character prefix. This trades some recall (an
eventName phrased in a way this classifier has not seen) for real
precision against every case captured so far -- same honest tradeoff
task 2.A recorded for its own English-only line-type keywords."""

from __future__ import annotations

from typing import Any

from .signal_model import Signal

_DESIGN_TENDER_STEMS = ("layihə-smeta", "layihə smeta", "layihəsmeta", "layihələn", "layihələm")


def classify_design_tender(event_name: str) -> bool:
    normalized = event_name.lower()
    return any(stem in normalized for stem in _DESIGN_TENDER_STEMS)


def build_design_tender_signal(
    item: dict[str, Any],
    *,
    raw_snapshot_id: int,
    observed_at: str,
    correlation_id: str,
) -> Signal:
    return Signal(
        signal_type="design_tender",
        source="etender",
        raw_snapshot_id=raw_snapshot_id,
        value={
            "event_id": item["eventId"],
            "event_name": item["eventName"],
            "publish_date": item.get("publishDate"),
            # Only ever observed False under the EventStatus=1 (open) filter
            # this task's job uses (see docs/decisions/OPEN-QUESTIONS.md) --
            # kept as a real fact, not a fabricated True case, ready for
            # whichever EventStatus value means "awarded" once decoded.
            "is_awarded": item.get("awardedParticipantName") is not None,
            "awarded_participant_name": item.get("awardedParticipantName"),
        },
        observed_at=observed_at,
        # A distinct ttl_class from the World Bank slice's "funding_decision"
        # -- a published design/TEO tender is a shorter-horizon, later-stage
        # signal than a funding decree. Exact duration remains TBD-TIS-01.
        ttl_class="design_phase_tender",
        # eTender is Azerbaijan's own official e-procurement portal -- same
        # first-party-official tier as the World Bank's own project API.
        confidence="official_source",
        object_customer=item.get("buyerOrganizationName"),
        # eTender's events-list item has no structured region or
        # project-category field -- both exist only as free text inside
        # eventName (e.g. "Qəbələ şəhərində", "yolların əsaslı təmiri").
        # Extracting either needs real gazetteer/NER work, not a guess.
        object_region=None,
        object_project_type=None,
        correlation_id=correlation_id,
    )
```

Save as `packages/tender/design_tender_signal.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_design_tender_signal.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/design_tender_signal.py tests/unit/test_design_tender_signal.py
git commit -m "feat(tender): design/TEO-tender signal classifier and builder"
```

---

## Task 4: `ingest_design_tender_signals_page()` — reuse the existing events-list ingest

**Files:**
- Modify: `packages/tender/etender_connector.py`
- Test: `tests/integration/test_design_tender_ingestion.py`

**Interfaces:**
- Consumes: `ingest_events_list_page` (existing, widened signature from Task 2),
  `classify_design_tender`, `build_design_tender_signal` (Task 3), `store_signal` (existing, from the
  World Bank slice).
- Produces: `async def ingest_design_tender_signals_page(conn, *, raw_body: bytes, payload: dict,
  query_params: dict, correlation_id: str, observed_at: str) -> list[int]` — returns stored signal ids;
  raises `SchemaDriftDetected` (propagated from `ingest_events_list_page`, not caught here — same
  precedent as every other `ingest_*` function in this file; the *job* layer catches it, see Task 5).

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

import pytest

from packages.tender.etender_connector import SchemaDriftDetected, ingest_design_tender_signals_page
from packages.tender.signals_store import list_signals

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


async def test_page1_stores_signals_only_for_real_design_tenders(engine):
    raw_body = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=QUERY_PARAMS,
            correlation_id="corr-design-page1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        # Page 1 (per Task 1's capture) is expected to be entirely real design/TEO tenders --
        # confirm every item on it classifies True, not a hand-picked subset.
        assert len(signal_ids) == len(payload["items"])

        rows = await list_signals(conn, signal_type="design_tender")
        stored_event_ids = {row["value"]["event_id"] for row in rows}
        assert stored_event_ids == {item["eventId"] for item in payload["items"]}


async def test_page2_excludes_the_real_false_positives(engine):
    raw_body = (FIXTURES / "design_tender_search_page2.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=QUERY_PARAMS,
            correlation_id="corr-design-page2",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        # 4 true negatives on this real page (events 356291, 356027 -- plural "layihələr-";
        # 356048, 355959 -- unrelated uses of "layihə"), 6 true positives.
        assert len(signal_ids) == 6

        rows = await list_signals(conn, signal_type="design_tender")
        stored_event_ids = {row["value"]["event_id"] for row in rows}
        assert stored_event_ids == {356192, 356143, 356140, 356055, 356039, 355972}
```

Save as `tests/integration/test_design_tender_ingestion.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_design_tender_ingestion.py -v`
Expected: FAIL with `ImportError: cannot import name 'ingest_design_tender_signals_page'`.

- [ ] **Step 3: Add `ingest_design_tender_signals_page` to `etender_connector.py`**

Append to `packages/tender/etender_connector.py` (after `ingest_events_list_page`, and add the two new
imports — `design_tender_signal`'s two functions and `signals_store.store_signal` — to the file's
existing import block; read the file first to place them correctly):

```python
async def ingest_design_tender_signals_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    query_params: dict[str, Any],
    correlation_id: str,
    observed_at: str,
) -> list[int]:
    version = await ingest_events_list_page(
        conn, raw_body=raw_body, payload=payload, query_params=query_params, correlation_id=correlation_id
    )

    signal_ids = []
    for item in payload["items"]:
        if not classify_design_tender(item["eventName"]):
            continue
        signal = build_design_tender_signal(
            item, raw_snapshot_id=version.raw_snapshot_id, observed_at=observed_at, correlation_id=correlation_id
        )
        signal_ids.append(await store_signal(conn, signal))
    return signal_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_design_tender_ingestion.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py tests/integration/test_design_tender_ingestion.py
git commit -m "feat(tender): derive design-tender signals from existing events-list ingestion"
```

---

## Task 5: Resumable pagination job over the real `Keyword=layihə` search

**Files:**
- Create: `packages/tender/design_tender_job.py`
- Test: `tests/integration/test_design_tender_job.py`

**Interfaces:**
- Consumes: `ingest_design_tender_signals_page`, `SchemaDriftDetected` (Task 4);
  `enqueue_exception` (existing, unchanged).
- Produces: `JOB_TYPE = "etender_design_tender_page_fetch"`; `FetchPage = Callable[[dict, int],
  Awaitable[tuple[bytes, dict]]]`; `async def process_design_tender_page(conn, job: Job, fetch_page:
  FetchPage, *, observed_at: str) -> dict[str, Any]` — checkpoint `next_page` (1 if never started),
  mirrors `bom_lines_job.py`'s exact resumability contract.

- [ ] **Step 1: Write the failing test (resume-after-failure, real distinct pages)**

```python
import json
from pathlib import Path

import pytest

from packages.platform.jobs import Job
from packages.tender.design_tender_job import process_design_tender_page

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


def _make_job(checkpoint: dict) -> Job:
    return Job(
        id=1,
        job_type="etender_design_tender_page_fetch",
        params={"query_params": QUERY_PARAMS},
        source="etender",
        range_start=None,
        range_end=None,
        contract_version="etender.events_list_page",
        correlation_id="corr-design-job-1",
        status="running",
        lease_owner="test-worker",
        attempt=1,
        max_attempts=5,
        checkpoint=checkpoint,
        last_error=None,
    )


async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    real_page1 = json.loads((FIXTURES / "design_tender_search_page1.raw.json").read_bytes())
    real_page2 = json.loads((FIXTURES / "design_tender_search_page2.raw.json").read_bytes())
    attempts = []

    async def fetch_page(query_params, page_number):
        attempts.append(page_number)
        if page_number == 1 and attempts.count(1) == 1:
            raise ConnectionError("simulated transient failure on first page")
        raw = (FIXTURES / f"design_tender_search_page{page_number}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        try:
            await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
            raised = False
        except ConnectionError:
            raised = True
        assert raised
        assert attempts == [1]

        job = _make_job(checkpoint={})
        result = await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2
        assert not result["done"]  # totalPages=15, page 1 of 15
        assert len(result["signal_ids"]) == len(real_page1["items"])

        job = _make_job(checkpoint={"next_page": 2})
        result = await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 3
        assert len(result["signal_ids"]) == 6  # 4 real true negatives on this page correctly excluded

        assert attempts == [1, 1, 2]  # page 1 fetched twice (failed, then succeeded), never skipped to page 2 early
```

Save as `tests/integration/test_design_tender_job.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_design_tender_job.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.design_tender_job'`.

- [ ] **Step 3: Write `design_tender_job.py`**

```python
"""Resumable pagination over eTender's own server-side Keyword=layihə
search (INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06). Mirrors bom_lines_job.py
and worldbank_pipeline_job.py's exact shape: `process_design_tender_page`
processes exactly one page, resuming from `job.checkpoint["next_page"]`
(1 if never started). Unlike scanning eTender's full unfiltered corpus,
this walks only the 147 real candidate tenders (15 real pages at
PageSize=10) the source's own search already narrowed down."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .etender_connector import ingest_design_tender_signals_page
from .schema_drift import SchemaDriftDetected

JOB_TYPE = "etender_design_tender_page_fetch"

FetchPage = Callable[[dict[str, Any], int], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_design_tender_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    query_params = job.params["query_params"]
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(query_params, next_page)

    try:
        signal_ids = await ingest_design_tender_signals_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            query_params=query_params,
            correlation_id=job.correlation_id,
            observed_at=observed_at,
        )
    except SchemaDriftDetected as drift_exc:
        exception_record = await enqueue_exception(
            conn,
            source="etender",
            exception_type="schema_drift",
            category="needs_human",
            reason=str(drift_exc),
            correlation_id=job.correlation_id,
            raw_ref=drift_exc.raw_snapshot_id,
            contract_name=drift_exc.contract_name,
        )
        total_pages = payload.get("totalPages")
        return {
            "next_page": next_page + 1,
            "done": total_pages is not None and next_page >= total_pages,
            "signal_ids": [],
            "exception_queue_id": exception_record.id,
        }

    total_pages = payload.get("totalPages")
    return {
        "next_page": next_page + 1,
        "done": total_pages is not None and next_page >= total_pages,
        "signal_ids": signal_ids,
    }
```

Save as `packages/tender/design_tender_job.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_design_tender_job.py -v`
Expected: PASS.

- [ ] **Step 5: Write and run the schema-drift-does-not-stall-pagination test (P305 precedent)**

Add to `tests/integration/test_design_tender_job.py`:
```python
async def test_schema_drift_on_one_page_does_not_stall_pagination(engine):
    real_page1 = json.loads((FIXTURES / "design_tender_search_page1.raw.json").read_bytes())
    drifted_page1 = {**real_page1, "unexpected_new_field": "drift"}

    async def fetch_page(query_params, page_number):
        if page_number == 1:
            return json.dumps(drifted_page1).encode(), drifted_page1
        raw = (FIXTURES / f"design_tender_search_page{page_number}.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        result = await process_design_tender_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2  # advanced past the drifted page, did not stall
        assert result["signal_ids"] == []
        assert result["exception_queue_id"] is not None
```

Run: `python -m pytest tests/integration/test_design_tender_job.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/design_tender_job.py tests/integration/test_design_tender_job.py
git commit -m "feat(tender): resumable pagination job for design-tender signals"
```

---

## Task 6: Live fetch (reuses existing egress trust — no new host)

**Files:**
- Modify: `packages/tender/etender_connector.py` (or a small new function alongside
  `ingest_design_tender_signals_page` — read the file to decide the cleanest placement)
- Test: `tests/security/test_design_tender_live_fetch.py`

**Interfaces:**
- Produces: `async def fetch_design_tender_page_live(conn, validator: EgressValidator, *,
  query_params: dict[str, Any], page_number: int) -> tuple[bytes, dict[str, Any]]` — matches Task 5's
  `FetchPage` signature so it can be passed directly as `design_tender_job.py`'s `fetch_page` argument
  at the `apps/worker` layer.

- [ ] **Step 1: Write the failing test (mirrors the World Bank slice's live-fetch test, same
  test-scoped trust pattern as the existing P304 SSRF test)**

```python
import pytest

from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressValidator
from packages.tender.etender_connector import fetch_design_tender_page_live

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


async def _trust(conn, host: str) -> None:
    await register_source(conn, host=host, allowed_schemes=["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


async def test_live_fetch_against_real_etender_design_search(engine):
    async with engine.begin() as conn:
        await _trust(conn, "etender.gov.az")
        validator = EgressValidator()
        _raw_body, payload = await fetch_design_tender_page_live(conn, validator, query_params=QUERY_PARAMS, page_number=1)
        assert payload["items"]
        assert int(payload["totalItems"]) >= 1
```

Save as `tests/security/test_design_tender_live_fetch.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/security/test_design_tender_live_fetch.py -v`
Expected: FAIL with `ImportError: cannot import name 'fetch_design_tender_page_live'`.

- [ ] **Step 3: Add the live-fetch function**

Append to `packages/tender/etender_connector.py` (add `urlencode` from `urllib.parse`,
`fetch_via_validator`, and `EgressValidator` to the file's imports if not already present — read the
file first):

```python
async def fetch_design_tender_page_live(
    conn: AsyncConnection,
    validator: EgressValidator,
    *,
    query_params: dict[str, Any],
    page_number: int,
) -> tuple[bytes, dict[str, Any]]:
    params = {**query_params, "PageNumber": page_number}
    url = f"https://etender.gov.az/api/events?{urlencode(params)}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"eTender events search returned HTTP {status} for {url!r}")
    return body, json.loads(body)
```

(`UnexpectedResponseStatus` and `json` may already need importing here too — this file did not
previously need either; check before adding a duplicate definition, and reuse
`worldbank_connector.py`'s `UnexpectedResponseStatus` class only if it makes sense to import across
modules, otherwise define a second small one-line exception class local to this file — either is fine,
prefer whichever avoids a cross-module import for a single trivial exception class.)

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/security/test_design_tender_live_fetch.py -v`
Expected: PASS — a real HTTP request reaches `etender.gov.az` through the full
validate-then-pinned-connect pipeline.

If this fails with a DNS/connection error, check `etender.gov.az` reachability directly first (`curl
--max-time 15 https://etender.gov.az/api/events/355920`) before assuming a code bug — this exact
flakiness happened once already during the World Bank slice (transient, unrelated to code, resolved
itself within the same session).

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py tests/security/test_design_tender_live_fetch.py
git commit -m "feat(tender): live egress-validated fetch for design-tender signals (reuses etender.gov.az trust)"
```

---

## Task 7: WORKLOG and Open Questions closeout

**Files:**
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

**Interfaces:** none (documentation only).

- [ ] **Step 1: Run the full gate one final time**

Run:
```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```
Expected: 0 failures, 0 ruff/mypy issues, v1-untouched PASS.

- [ ] **Step 2: Append a WORKLOG entry**

Follow the exact format of every prior entry (date, **Сделано**, **Вывод полного прогона** with the
real output from Step 1, **Дальше**, **Блокеры**). State plainly: (a) this is the second signal source
for `P309`/`TENDER_INTELLIGENCE_SPEC.md` §5.2, in a genuinely different category (design/TEO tenders)
from the first (World Bank donor pipeline); (b) it needed zero new external hosts/egress trust because
it derives from eTender data task 1.A's connector already ingests; (c) it closed the previously-deferred
"events-list filter-aware identity" gap from task 1.E; (d) the classifier's real, bounded
precision/recall tradeoff (Global Constraints above) is recorded, not hidden; (e) four of the six
`TENDER_INTELLIGENCE_SPEC.md` §5.2 signal categories (decrees, procurement plans, budgets, vacancies)
and the other three donor institutions (ADB/EBRD/AIIB) remain unstarted.

- [ ] **Step 3: Record open questions**

Add an entry to `docs/decisions/OPEN-QUESTIONS.md`:
- `EventStatus`'s real value-to-meaning mapping is still undecoded (this task only used the
  already-known `EventStatus=1` = "open" from the 1.A follow-up session) — `is_awarded` on every real
  `design_tender` signal captured so far is `False` because open-only tenders were searched; a future
  task should decode which `EventStatus` value means "awarded/closed" to get the stronger signal the
  spec's own worked example describes ("тендер на ТЭО выигран" = won, not just published).
  Non-blocking.
- `object_region`/`object_project_type` extraction from `eventName` free text (Azerbaijani place names,
  work-category keywords) is real, valuable, unattempted work for a future task — not a decision the
  owner needs to make now, but should not be silently assumed solved by this task's `None` values.

- [ ] **Step 4: Commit**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(tender): close out task 2.B second slice (design/TEO-tender signals)"
```

---

## Self-review notes (for whoever executes this plan)

- **Spec coverage:** `TENDER_INTELLIGENCE_SPEC.md` §5.2's "тендеры на ТЭО/проектирование" category is
  now a second, real, proven `Signal` source — genuinely different from the donor-pipeline category
  (different object binding shape, different `ttl_class`, keyword-classification risk profile instead
  of a stable external API contract). `P309` is proven for a second instance.
- **No placeholders:** every code block traces to real captured data (2026-08-05 reconnaissance) or an
  existing, already-proven mechanism (`ingest_events_list_page`, `Signal`, `store_signal`,
  `enqueue_exception`, `fetch_via_validator`) reused, not reinvented.
- **Real known limitation, stated not hidden:** the classifier's `layihə` generic-vs-specific ambiguity,
  and the unresolved `EventStatus` code mapping, are both recorded in Task 7 rather than glossed over.
