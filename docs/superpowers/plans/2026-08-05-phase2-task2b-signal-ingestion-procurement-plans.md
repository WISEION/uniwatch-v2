# Phase 2, Task 2.B — Signal ingestion (annual procurement-plan slice, third source) — Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A third `Signal` source for `TENDER_INTELLIGENCE_SPEC.md` §5.2 — Azerbaijan's real annual
procurement plans (`Годовые планы закупок`), published on eTender itself under `/main/purchase-plan`.
Reuses 100% of already-trusted eTender infrastructure (same host, same egress trust, same generic
contract/drift/job mechanisms) — no new external site. Unlike the World Bank slice, this one has
**confirmed real region-level object overlap** with the existing design-tender signals: both
`ZAQATALA RAYONU İCRA HAKİMİYYƏTİ` (design tenders) and multiple real Zaqatala-based organizations
submitting procurement plans (e.g. `ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ`) canonicalize to
the same `object_region = "Zaqatala"` via the already-built `az_region_identity.py` — the first genuine
cross-category intersection this project has found.

**Real API contract, discovered by static analysis of eTender's Angular bundle (`main.f5154a38aaa91629.js`)
and confirmed live (2026-08-05) — not guessed:**
- `GET /api/app?PageSize={n}&PageNumber={n}&Year={year}[&BuyerOrganizationName={filter}]` — paged list
  of procurement-plan submissions. Real, live-verified: `Year=2026` alone returns `totalItems: 1413`
  across `totalPages: 283` (`PageSize=5`); `Year=2026&BuyerOrganizationName=ZAQATALA` returns
  `totalItems: 33`. `Year` is required (bound to the current year client-side by default); valid years
  come from `GET /api/app/years` (live-verified: `[2027, 2026, 2025, 2024, 2023, 2022, 2021, 2020, 2019]`
  — 2027 already has planning data, a genuinely forward-looking real fact).
- `GET /api/app/{id}` — one organization's plan header (`id`, `year`, `organizationName`).
- `GET /api/app/{id}/versions` — **the literal "changes to them" half of this signal category**: a
  real plan's version/amendment history (`id`, `date`, `createReason` — live-verified example:
  `"İlk satınalma planının yaradılması"`, "creation of the first purchase plan"). **Not built by this
  plan** (see Global Constraints) — recorded here because it is the natural next slice.
- `GET /api/app-version/{versionId}/items?PageSize={n}&PageNumber={n}[&Keyword={filter}]` — the actual
  planned-purchase line items for one plan version (`name`, `month`, `deliveryAddress`,
  `deliveryTime`, `eventType`). **Not built by this plan** either — see Global Constraints.

**Architecture:** `etender_contract.py` gets `APP_LIST_PAGE_CONTRACT` (page wrapper, same shape family
as `EVENTS_LIST_PAGE_CONTRACT`) and `APP_ITEM_CONTRACT` (per-plan item). A new
`packages/tender/procurement_plan_signal.py` gets `build_procurement_plan_signal()`, reusing the
existing `Signal` dataclass and `az_region_identity.canonicalize_region()` unchanged.
`etender_connector.py` gets `ingest_procurement_plan_page()` (raw → drift → one `Signal` per plan
submission) and `fetch_procurement_plan_page_live()`. `procurement_plan_job.py` gets resumable
pagination, mirroring `design_tender_job.py`'s exact shape but keyed on `Year`/`PageNumber` instead of a
keyword search.

## Global Constraints

- **Scope is the list endpoint only** (`GET /api/app`) — one signal per plan *submission*, using its
  `createDate` as `observed_at`. The `/versions` (per-plan change history) and `/app-version/{id}/items`
  (line items) endpoints are real and confirmed working but are **not called by this plan** — fetching
  versions/items requires one extra API call *per plan* (1413+ plans for 2026 alone), a real
  rate/scale concern that deserves its own scoped task, not a silent addition here. This is the
  incremental-slice discipline task 1.A used splitting eTender's three original resources one at a
  time — recorded honestly in Task 4, not silently dropped.
- No fabricated data. Every example value (`ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ`,
  `totalItems: 1413`, the version's `createReason` text) comes from a real, live capture made
  2026-08-05 during this task's reconnaissance.
- **Filter-aware identity from the start** — `APP_LIST_PAGE_CONTRACT.identity_query_keys` includes
  `Year`, `PageNumber`, and `BuyerOrganizationName` together, not just `PageNumber`. This is the same
  lesson the design-tender slice had to retrofit onto `EVENTS_LIST_PAGE_CONTRACT` after the fact — this
  resource gets it right on the first pass.
- No new egress trust, no new migration. `etender.gov.az` is already trusted (test-scoped) in the
  existing SSRF suite and both prior signal-source live-fetch tests; `signals` (from the World Bank
  slice) is reused as-is.
- `object_region` is populated via the *existing* `canonicalize_region()` applied to
  `organizationName` — no changes to `az_region_identity.py` in this plan (its known-region set already
  includes `Zaqatala`, which is what this plan's own real fixture data needs). Extending the gazetteer
  further is separate, future work if a captured plan names an unobserved region.
- `object_project_type` stays `None` — `eventType` (seen on line *items*, not on the list endpoint this
  plan ingests) is an undecoded numeric code; decoding it is real future work, not guessed at here.

---

## Task 1: Real fixture capture — procurement-plan list pages

**Files:**
- Create: `fixtures/tender-snapshots/etender/app_list_page1_2026.raw.json`
- Create: `fixtures/tender-snapshots/etender/app_list_zaqatala_2026.raw.json`
- Modify: `fixtures/tender-snapshots/etender/MANIFEST.md`

- [ ] **Step 1: Capture an unfiltered 2026 page**

Run:
```bash
curl -s "https://etender.gov.az/api/app?PageSize=10&PageNumber=1&Year=2026" \
  -o fixtures/tender-snapshots/etender/app_list_page1_2026.raw.json
```

Expected shape (verified live 2026-08-05): `totalItems: 1413`, `totalPages: 142` (at `PageSize=10`),
`items` each with `id`, `organizationName`, `year: 2026`, `createDate`. First real id observed: `16820`
(`ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ.`).

- [ ] **Step 2: Capture a Zaqatala-filtered page — the real cross-category overlap case**

Run:
```bash
curl -s "https://etender.gov.az/api/app?PageSize=10&PageNumber=1&Year=2026&BuyerOrganizationName=ZAQATALA" \
  -o fixtures/tender-snapshots/etender/app_list_zaqatala_2026.raw.json
```

Expected shape: `totalItems: 33`, 10 real Zaqatala-region organizations (e.g. `ZAQATALA RAYON GİGİYENA
VƏ EPİDEMİOLOGİYA MƏRKƏZİ.`, `AZƏRBAYCAN RESPUBLİKASI ZAQATALA RAYONU İCRA HAKİMİYYƏTİ ÜÇÜNCÜ TALA KƏND
İNZİBATİ ƏRAZİ DAİRƏSİ ÜZRƏ NÜMAYƏNDƏSİ`) — every one of these canonicalizes to `object_region =
"Zaqatala"` via the existing `canonicalize_region()`, the same object the design-tender slice's real
`ZAQATALA RAYONU İCRA HAKİMİYYƏTİ` signals already populate.

- [ ] **Step 3: Compute checksums and update the manifest**

Run: `sha256sum fixtures/tender-snapshots/etender/app_list_page1_2026.raw.json fixtures/tender-snapshots/etender/app_list_zaqatala_2026.raw.json`

Append a new table-row block and "What these confirm" bullet to
`fixtures/tender-snapshots/etender/MANIFEST.md` (read the file first, follow its exact existing style)
noting: real API discovered via static bundle analysis (`main.f5154a38aaa91629.js`), not documentation;
`Year` is required, valid years `2019`-`2027` (`/api/app/years`, live-verified); the Zaqatala-filtered
page is frozen specifically because it proves real cross-category object overlap with
`design_tender_search_page1.raw.json`'s `ZAQATALA RAYONU İCRA HAKİMİYYƏTİ` signals.

- [ ] **Step 4: Commit**

```bash
git add fixtures/tender-snapshots/etender/app_list_page1_2026.raw.json \
        fixtures/tender-snapshots/etender/app_list_zaqatala_2026.raw.json \
        fixtures/tender-snapshots/etender/MANIFEST.md
git commit -m "test(tender): capture real eTender procurement-plan fixtures for task 2.B (third source)"
```

---

## Task 2: `APP_LIST_PAGE_CONTRACT`/`APP_ITEM_CONTRACT`

**Files:**
- Modify: `packages/tender/etender_contract.py`
- Test: `tests/unit/test_app_list_contract_fixtures.py`

- [ ] **Step 1: Write the failing test**

```python
import json
from pathlib import Path

from packages.tender.etender_contract import APP_ITEM_CONTRACT, APP_LIST_PAGE_CONTRACT
from packages.tender.schema_drift import detect_schema_drift, detect_schema_drift_over_items

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load(name: str) -> dict:
    return json.loads((FIXTURES / name).read_text())


def test_page1_fixture_is_drift_free():
    payload = _load("app_list_page1_2026.raw.json")
    assert not detect_schema_drift(APP_LIST_PAGE_CONTRACT, payload).has_drift


def test_zaqatala_fixture_is_drift_free():
    payload = _load("app_list_zaqatala_2026.raw.json")
    assert not detect_schema_drift(APP_LIST_PAGE_CONTRACT, payload).has_drift


def test_every_item_in_both_pages_is_drift_free():
    for name in ("app_list_page1_2026.raw.json", "app_list_zaqatala_2026.raw.json"):
        payload = _load(name)
        drift = detect_schema_drift_over_items(APP_ITEM_CONTRACT, payload["items"])
        assert not drift.has_drift, f"{name}: {drift}"
```

Save as `tests/unit/test_app_list_contract_fixtures.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_app_list_contract_fixtures.py -v`
Expected: FAIL — `ImportError: cannot import name 'APP_LIST_PAGE_CONTRACT'`.

- [ ] **Step 3: Add the contracts to `etender_contract.py`**

Append (read the file first to match its exact existing style/imports — `FieldSpec`/`SourceContract`
are already imported):

```python
# Captured from fixtures/tender-snapshots/etender/app_list_page{1,zaqatala}_2026.raw.json (task 2.B,
# procurement-plan signal slice). API discovered by static analysis of eTender's Angular bundle
# (main.f5154a38aaa91629.js), not documentation -- confirmed live 2026-08-05.
APP_LIST_PAGE_CONTRACT = SourceContract(
    name="etender.app_list_page",
    identity_query_keys=("Year", "PageNumber", "BuyerOrganizationName"),
    fields=(
        FieldSpec("currentPage", "number"),
        FieldSpec("totalPages", "number"),
        FieldSpec("pageSize", "number"),
        FieldSpec("itemsInPage", "number"),
        FieldSpec("totalItems", "number"),
        FieldSpec("items", "array"),
        FieldSpec("hasPreviousPage", "boolean"),
        FieldSpec("hasNextPage", "boolean"),
        FieldSpec("firstItem", "number"),
        FieldSpec("lastItem", "number"),
    ),
)

APP_ITEM_CONTRACT = SourceContract(
    name="etender.app_list_page.item",
    identity_query_keys=("id",),
    fields=(
        FieldSpec("id", "number"),
        FieldSpec("organizationName", "string"),
        FieldSpec("year", "number"),
        FieldSpec("createDate", "string"),
    ),
)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_app_list_contract_fixtures.py -v`
Expected: all 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_contract.py tests/unit/test_app_list_contract_fixtures.py
git commit -m "feat(tender): eTender procurement-plan list source contract"
```

---

## Task 3: `procurement_plan_signal.py`

**Files:**
- Create: `packages/tender/procurement_plan_signal.py`
- Test: `tests/unit/test_procurement_plan_signal.py`

- [ ] **Step 1: Write the failing test**

```python
from packages.tender.procurement_plan_signal import build_procurement_plan_signal


def test_build_signal_from_real_zaqatala_plan():
    # Real item, fixtures/tender-snapshots/etender/app_list_zaqatala_2026.raw.json.
    item = {
        "id": 16820,
        "organizationName": "ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ.",
        "year": 2026,
        "createDate": "2026-08-05T12:13:51.8766677",
    }
    signal = build_procurement_plan_signal(
        item, raw_snapshot_id=201, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-app-1"
    )
    assert signal.signal_type == "procurement_plan"
    assert signal.source == "etender"
    assert signal.raw_snapshot_id == 201
    assert signal.value["app_id"] == 16820
    assert signal.value["year"] == 2026
    assert signal.ttl_class == "procurement_plan"
    assert signal.confidence == "official_source"
    assert signal.object_customer == "ZAQATALA RAYON GİGİYENA VƏ EPİDEMİOLOGİYA MƏRKƏZİ."
    # The real cross-category intersection: same canonicalizer, same region as the
    # design-tender slice's real "ZAQATALA RAYONU İCRA HAKİMİYYƏTİ" signals.
    assert signal.object_region == "Zaqatala"


def test_build_signal_region_none_for_non_regional_organization():
    item = {
        "id": 99999,
        "organizationName": "Azərbaycan Respublikası Dövlət Neft Fondu",
        "year": 2026,
        "createDate": "2026-08-05T12:00:00",
    }
    signal = build_procurement_plan_signal(
        item, raw_snapshot_id=202, observed_at="2026-08-05T12:00:00+00:00", correlation_id="corr-app-2"
    )
    assert signal.object_region is None
```

Save as `tests/unit/test_procurement_plan_signal.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_procurement_plan_signal.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `procurement_plan_signal.py`**

```python
"""Annual procurement-plan signal (TENDER_INTELLIGENCE_SPEC.md §5.2, P309,
third signal source/category). List-endpoint slice only -- one Signal per
plan *submission*; the plan's own version/amendment history ("changes to
them", GET /api/app/{id}/versions) and line items (GET
/api/app-version/{id}/items) are real, confirmed-working eTender
endpoints but are deliberately not consumed here (each needs a per-plan
follow-up call -- a real scale concern for 1413+ plans/year, scoped to a
future task, not silently skipped)."""

from __future__ import annotations

from typing import Any

from .az_region_identity import canonicalize_region
from .signal_model import Signal


def build_procurement_plan_signal(
    item: dict[str, Any],
    *,
    raw_snapshot_id: int,
    observed_at: str,
    correlation_id: str,
) -> Signal:
    return Signal(
        signal_type="procurement_plan",
        source="etender",
        raw_snapshot_id=raw_snapshot_id,
        value={
            "app_id": item["id"],
            "organization_name": item["organizationName"],
            "year": item["year"],
            "create_date": item["createDate"],
        },
        observed_at=observed_at,
        # A budget/planning-cycle signal -- distinct from the World Bank
        # slice's "funding_decision" and the design-tender slice's
        # "design_phase_tender". Exact duration remains TBD-TIS-01.
        ttl_class="procurement_plan",
        # eTender is Azerbaijan's own official e-procurement portal --
        # same first-party-official tier as the other two eTender-derived
        # and World Bank signal types.
        confidence="official_source",
        object_customer=item["organizationName"],
        object_region=canonicalize_region(item["organizationName"]),
        object_project_type=None,
        correlation_id=correlation_id,
    )
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_procurement_plan_signal.py -v`
Expected: both PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/procurement_plan_signal.py tests/unit/test_procurement_plan_signal.py
git commit -m "feat(tender): annual procurement-plan signal builder"
```

---

## Task 4: `ingest_procurement_plan_page()` + real cross-category intersection proof

**Files:**
- Modify: `packages/tender/etender_connector.py`
- Test: `tests/integration/test_procurement_plan_ingestion.py`

**Interfaces:**
- Produces: `async def ingest_procurement_plan_page(conn, *, raw_body: bytes, payload: dict, year: int,
  page_number: int, buyer_organization_name: str, correlation_id: str, observed_at: str) -> list[int]`
  — same raw→drift→signal shape as `ingest_design_tender_signals_page`, but standalone (no existing
  generic ingest function to reuse here, since this is a new resource, not a derived view of one).

- [ ] **Step 1: Write the failing test, including the real cross-category proof**

```python
import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page, ingest_procurement_plan_page
from packages.tender.signals_store import list_signals_by_object_region

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


async def test_zaqatala_page_stores_one_signal_per_real_plan(engine):
    raw_body = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_procurement_plan_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-app-page1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        assert len(signal_ids) == len(payload["items"])

        rows = await list_signals_by_object_region(conn, object_region="Zaqatala")
        stored_ids = {row["value"].get("app_id") for row in rows if row["signal_type"] == "procurement_plan"}
        assert stored_ids == {item["id"] for item in payload["items"]}


async def test_real_cross_category_intersection_on_zaqatala(engine):
    # The actual proof this plan exists to deliver: a design-tender signal AND a
    # procurement-plan signal, from two different real organizations, both anchor
    # to the same real object_region -- the first genuine cross-category overlap
    # this project has found (see docs/decisions/OPEN-QUESTIONS.md, 2026-08-05).
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)
    app_raw = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
    app_payload = json.loads(app_raw)

    design_query_params = {
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

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=design_query_params,
            correlation_id="corr-intersect-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        await ingest_procurement_plan_page(
            conn,
            raw_body=app_raw,
            payload=app_payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-intersect-2",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        rows = await list_signals_by_object_region(conn, object_region="Zaqatala")
        signal_types = {row["signal_type"] for row in rows}
        assert signal_types == {"design_tender", "procurement_plan"}
```

Save as `tests/integration/test_procurement_plan_ingestion.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_procurement_plan_ingestion.py -v`
Expected: FAIL — `ImportError: cannot import name 'ingest_procurement_plan_page'`.

- [ ] **Step 3: Add `ingest_procurement_plan_page` to `etender_connector.py`**

Append (add `APP_ITEM_CONTRACT`, `APP_LIST_PAGE_CONTRACT` to the existing `etender_contract` import, and
`build_procurement_plan_signal` alongside the existing `design_tender_signal` import — read the file
first to place them correctly):

```python
async def ingest_procurement_plan_page(
    conn: AsyncConnection,
    *,
    raw_body: bytes,
    payload: dict[str, Any],
    year: int,
    page_number: int,
    buyer_organization_name: str,
    correlation_id: str,
    observed_at: str,
) -> list[int]:
    identity_key = canonical_identity(
        APP_LIST_PAGE_CONTRACT,
        {"Year": str(year), "PageNumber": str(page_number), "BuyerOrganizationName": buyer_organization_name},
    )

    snapshot_id = await save_raw_snapshot(
        conn,
        source="etender",
        resource_type=APP_LIST_PAGE_CONTRACT.name,
        identity_key=identity_key,
        raw_body=raw_body,
        contract_version=APP_LIST_PAGE_CONTRACT.name,
        correlation_id=correlation_id,
    )

    drift = detect_schema_drift(APP_LIST_PAGE_CONTRACT, payload)
    drifted_contract_name = APP_LIST_PAGE_CONTRACT.name
    if not drift.has_drift:
        drift = detect_schema_drift_over_items(APP_ITEM_CONTRACT, payload["items"])
        drifted_contract_name = APP_ITEM_CONTRACT.name

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
    for item in payload["items"]:
        signal = build_procurement_plan_signal(
            item, raw_snapshot_id=snapshot_id, observed_at=observed_at, correlation_id=correlation_id
        )
        signal_ids.append(await store_signal(conn, signal))
    return signal_ids
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_procurement_plan_ingestion.py -v`
Expected: both PASS — including the real cross-category intersection proof.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/etender_connector.py tests/integration/test_procurement_plan_ingestion.py
git commit -m "feat(tender): procurement-plan ingestion, proves real cross-category signal intersection on Zaqatala"
```

---

## Task 5: Resumable pagination job + live fetch

**Files:**
- Create: `packages/tender/procurement_plan_job.py`
- Test: `tests/integration/test_procurement_plan_job.py`
- Modify: `packages/tender/etender_connector.py` (live fetch)
- Test: `tests/security/test_procurement_plan_live_fetch.py`

- [ ] **Step 1: Write the failing job test**

```python
import json
from pathlib import Path

from packages.platform.jobs import Job
from packages.tender.procurement_plan_job import process_procurement_plan_page

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _make_job(checkpoint: dict) -> Job:
    return Job(
        id=1,
        job_type="etender_procurement_plan_page_fetch",
        params={"year": 2026, "buyer_organization_name": "ZAQATALA"},
        source="etender",
        range_start=None,
        range_end=None,
        contract_version="etender.app_list_page",
        correlation_id="corr-app-job-1",
        status="running",
        lease_owner="test-worker",
        attempt=1,
        max_attempts=5,
        checkpoint=checkpoint,
        last_error=None,
    )


async def test_page_fetch_failure_resumes_same_page_not_next(engine):
    real_page = json.loads((FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes())
    attempts = []

    async def fetch_page(year, page_number, buyer_organization_name):
        attempts.append(page_number)
        if page_number == 1 and attempts.count(1) == 1:
            raise ConnectionError("simulated transient failure")
        raw = (FIXTURES / "app_list_zaqatala_2026.raw.json").read_bytes()
        return raw, json.loads(raw)

    async with engine.begin() as conn:
        job = _make_job(checkpoint={})
        try:
            await process_procurement_plan_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
            raised = False
        except ConnectionError:
            raised = True
        assert raised
        assert attempts == [1]

        job = _make_job(checkpoint={})
        result = await process_procurement_plan_page(conn, job, fetch_page, observed_at="2026-08-05T12:00:00+00:00")
        assert result["next_page"] == 2
        assert not result["done"]  # totalItems=33, pageSize=10 -> totalPages=4
        assert len(result["signal_ids"]) == len(real_page["items"])
        assert attempts == [1, 1]
```

Save as `tests/integration/test_procurement_plan_job.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_procurement_plan_job.py -v`
Expected: FAIL — `ModuleNotFoundError`.

- [ ] **Step 3: Write `procurement_plan_job.py`**

Mirror `design_tender_job.py`'s exact structure (`process_design_tender_page` as the template):
checkpoint `next_page` (1 if never started), call `ingest_procurement_plan_page`, catch
`SchemaDriftDetected` into the exception queue and advance past the drifted page (P305 precedent),
`done = next_page >= payload["totalPages"]`.

```python
"""Resumable pagination over eTender's own procurement-plan list endpoint
(INV-03, FR-JOB-04, FR-JOB-05, FR-JOB-06). Mirrors design_tender_job.py's
exact shape."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from packages.platform.exception_queue import enqueue_exception
from packages.platform.jobs import Job

from .etender_connector import ingest_procurement_plan_page
from .schema_drift import SchemaDriftDetected

JOB_TYPE = "etender_procurement_plan_page_fetch"

FetchPage = Callable[[int, int, str], Awaitable[tuple[bytes, dict[str, Any]]]]


async def process_procurement_plan_page(
    conn: AsyncConnection, job: Job, fetch_page: FetchPage, *, observed_at: str
) -> dict[str, Any]:
    year = job.params["year"]
    buyer_organization_name = job.params.get("buyer_organization_name", "")
    next_page = job.checkpoint.get("next_page", 1)

    raw_body, payload = await fetch_page(year, next_page, buyer_organization_name)

    try:
        signal_ids = await ingest_procurement_plan_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            year=year,
            page_number=next_page,
            buyer_organization_name=buyer_organization_name,
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

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_procurement_plan_job.py -v`
Expected: PASS.

- [ ] **Step 5: Live-fetch test, same pattern as the other two slices' live-fetch tests**

```python
from packages.platform.egress.registry import promote_to_trusted, register_source
from packages.platform.egress.validator import EgressValidator
from packages.tender.etender_connector import fetch_procurement_plan_page_live


async def _trust(conn, host: str) -> None:
    await register_source(conn, host=host, allowed_schemes=["https"], registered_by="test")
    await promote_to_trusted(conn, host=host, scanner_run_reference="test-scan")


async def test_live_fetch_against_real_etender_procurement_plan_search(engine):
    async with engine.begin() as conn:
        await _trust(conn, "etender.gov.az")
        validator = EgressValidator()
        _raw_body, payload = await fetch_procurement_plan_page_live(
            conn, validator, year=2026, page_number=1, buyer_organization_name="ZAQATALA"
        )
        assert payload["items"]
        assert int(payload["totalItems"]) >= 1
```

Save as `tests/security/test_procurement_plan_live_fetch.py`. Add `fetch_procurement_plan_page_live` to
`etender_connector.py`, same shape as `fetch_design_tender_page_live`:

```python
async def fetch_procurement_plan_page_live(
    conn: AsyncConnection,
    validator: EgressValidator,
    *,
    year: int,
    page_number: int,
    buyer_organization_name: str = "",
) -> tuple[bytes, dict[str, Any]]:
    params = {"PageSize": 10, "PageNumber": page_number, "Year": year}
    if buyer_organization_name:
        params["BuyerOrganizationName"] = buyer_organization_name
    url = f"https://etender.gov.az/api/app?{urlencode(params)}"
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"eTender app-list search returned HTTP {status} for {url!r}")
    return body, json.loads(body)
```

- [ ] **Step 6: Run test to verify it passes**

Run: `python -m pytest tests/security/test_procurement_plan_live_fetch.py -v`
Expected: PASS (real network request).

- [ ] **Step 7: Commit**

```bash
git add packages/tender/procurement_plan_job.py packages/tender/etender_connector.py \
        tests/integration/test_procurement_plan_job.py tests/security/test_procurement_plan_live_fetch.py
git commit -m "feat(tender): resumable pagination + live fetch for procurement-plan signals"
```

---

## Task 6: WORKLOG and Open Questions

- [ ] **Step 1: Run the full gate**

Run:
```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```

- [ ] **Step 2: WORKLOG entry**

State plainly: (a) third signal source, third category, real API found via static bundle analysis
(same method used for eTender's original list endpoint in the 2026-08-04 follow-up session — same
technique, applied to a new resource, without needing a live browser trace this time); (b) this is the
**first genuine cross-category object intersection** found in this project — real Zaqatala-region
signals now exist from two independent categories (design tenders, procurement plans); (c) the plan's
own version/amendment history and line-items endpoints are real, confirmed-working, and deliberately
not consumed yet (per-plan N+1 call cost, scoped separately).

- [ ] **Step 3: Open Questions entry**

Record: `/api/app/{id}/versions` and `/api/app-version/{id}/items` remain real, unconsumed endpoints —
the natural next slice for "changes to procurement plans" and for enriching signals with actual planned
purchase subjects/timing/delivery addresses (which would give even better region granularity than
`organizationName` alone). `eventType` (seen on line items) remains an undecoded numeric code.

- [ ] **Step 4: Commit**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(tender): close out procurement-plan signal slice, record real cross-category intersection"
```

---

## Self-review notes

- **Spec coverage:** `TENDER_INTELLIGENCE_SPEC.md` §5.2's "annual procurement plans" category is now a
  third real, proven `Signal` source. The "and changes to them" half of the category name is
  deliberately deferred (Global Constraints), not silently claimed as done.
- **The real payoff:** Task 4's second test is the actual point of this plan — proving, with 100% real
  captured data, that two independent signal categories now share a real object
  (`object_region = "Zaqatala"`). This directly unblocks whatever comes next for task 2.C's
  composite-trigger work, which had nothing real to prove itself against before this.
