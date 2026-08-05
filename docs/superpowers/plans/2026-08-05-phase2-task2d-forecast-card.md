# Phase 2, Task 2.D — Forecast card (evidence chain only) Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention for Phase 0/1/2 tasks (see `docs/reports/WORKLOG.md`). No subagent
> handoff. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the real, non-fabricated slice of `TENDER_INTELLIGENCE_SPEC.md` §5.4's forecast card —
a verifiable evidence chain for one object (`P311`), gated on the already-real `is_composite` boolean
from task 2.C, with a budget estimate surfaced only when a signal's own source document actually
carries one. Three calibrated probabilities, a publication-window estimate, and Next Best Action are
explicitly not built — all three need `TBD-TIS-02`, which doesn't exist yet.

**Architecture:** A pure assembler (`packages/tender/forecast_card.py`, no DB/network, same shape as
`object_intersection.py`) takes an object's accumulated signal rows and returns `ForecastCard | None` —
`None` when `detect_intersection(...).is_composite` is `False`, refusing to assemble a card at all
below that bar, the same intent as P311's "card only at threshold" just gated on a real fact instead of
an uncalibrated percentage. A thin async wrapper in `signals_store.py` composes it with
`list_signals_by_object_region`, mirroring `detect_object_region_intersection`'s exact shape from task 2.C.

**Tech Stack:** Python 3.12, SQLAlchemy 2.0 async, pytest + pytest-asyncio, testcontainers Postgres — no
new dependencies, no schema migration (reuses the existing `signals` table and `list_signals_by_object_region`).

## Global Constraints

- **`is_composite` substitutes for the real (missing) probability threshold** — this is a real
  deviation from §5.4's literal "≥50%" wording, not a hidden shortcut. It must be recorded in
  `docs/decisions/OPEN-QUESTIONS.md` (Task 3), not silently presented as satisfying P311's letter.
- **Do not build:** the three probabilities, the publication window, or Next Best Action. All three
  need `TBD-TIS-02` (no calibrated model exists — see task 2.C's own OPEN-QUESTIONS.md entry,
  2026-08-05). Omit them entirely — do not stub with a placeholder value or a fake number.
- **Do not build delivery** (weekly digest / urgent alert) — a separate future task, not part of
  assembling the card itself.
- **Budget estimate is real, not calibrated** — surface whatever monetary field a signal's own source
  document already carries, verbatim. Today only `donor_pipeline_project` signals carry one
  (`total_amount_usd_text`, plus `url`) — `design_tender`/`procurement_plan` signals carry none, so
  `budget_estimate` is honestly `None` for an object accumulating only those types.
- **Do not invent a URL** for signal types that don't carry one (`design_tender`/`procurement_plan`).
  Use `raw_snapshot_id` (always present, a real verifiable pointer to the raw evidence) as the honest
  "link" surrogate for those entries — record this precisely as a gap in Task 3's OPEN-QUESTIONS.md
  entry, not silently.
- **No new external fetch needed.** Both proof cases (Zaqatala composite card, Siyəzən no card) are
  provable entirely from fixtures already frozen in `fixtures/tender-snapshots/etender/` — do not add a
  live-fetch test for this task.
- **Every commit lands via a feature branch + PR + green CI**, not a direct push to `master` — GitHub
  branch protection requires Fast gate + Full gate to pass first.
- Every requirement ID used must trace to `TENDER_INTELLIGENCE_SPEC.md` §5.4, `P311`, `TBD-TIS-01`,
  `TBD-TIS-02` (all already-existing IDs) — do not invent a new one.

---

## Task 1: `forecast_card.py` — pure evidence-chain assembler

**Files:**
- Create: `packages/tender/forecast_card.py`
- Test: `tests/unit/test_forecast_card.py`

**Interfaces:**
- Consumes: `detect_intersection` from `packages/tender/object_intersection.py` (task 2.C, unchanged).
- Produces: `@dataclass(frozen=True) class ForecastCard` with fields `object_region: str`,
  `is_composite: bool`, `signal_types: frozenset[str]`, `budget_estimate: dict[str, Any] | None`,
  `evidence_chain: tuple[dict[str, Any], ...]`; and
  `build_forecast_card(object_region: str, signal_rows: Sequence[dict[str, Any]]) -> ForecastCard | None`
  — pure function, no DB, no network.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for the pure forecast-card assembler (TENDER_INTELLIGENCE_SPEC.md
§5.4, P311)."""

from packages.tender.forecast_card import build_forecast_card


def test_non_composite_object_has_no_card():
    rows = [
        {
            "signal_type": "design_tender",
            "source": "etender",
            "raw_snapshot_id": 1,
            "value": {"event_id": 100},
            "observed_at": "2026-08-01T00:00:00+00:00",
        },
    ]
    assert build_forecast_card("Siyəzən", rows) is None


def test_composite_object_without_budget_signal_has_no_budget_estimate():
    rows = [
        {
            "signal_type": "design_tender",
            "source": "etender",
            "raw_snapshot_id": 1,
            "value": {"event_id": 100},
            "observed_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "signal_type": "procurement_plan",
            "source": "etender",
            "raw_snapshot_id": 2,
            "value": {"app_id": 200},
            "observed_at": "2026-08-02T00:00:00+00:00",
        },
    ]
    card = build_forecast_card("Zaqatala", rows)

    assert card is not None
    assert card.object_region == "Zaqatala"
    assert card.is_composite is True
    assert card.signal_types == frozenset({"design_tender", "procurement_plan"})
    assert card.budget_estimate is None
    assert len(card.evidence_chain) == 2
    assert card.evidence_chain[0]["signal_type"] == "design_tender"
    assert card.evidence_chain[0]["raw_snapshot_id"] == 1
    assert card.evidence_chain[0]["observed_at"] == "2026-08-01T00:00:00+00:00"
    assert card.evidence_chain[1]["signal_type"] == "procurement_plan"


def test_composite_object_with_donor_pipeline_signal_has_budget_estimate():
    rows = [
        {
            "signal_type": "design_tender",
            "source": "etender",
            "raw_snapshot_id": 1,
            "value": {"event_id": 100},
            "observed_at": "2026-08-01T00:00:00+00:00",
        },
        {
            "signal_type": "donor_pipeline_project",
            "source": "worldbank_projects_api",
            "raw_snapshot_id": 3,
            "value": {
                "total_amount_usd_text": "250,000,000",
                "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P999999",
            },
            "observed_at": "2026-08-03T00:00:00+00:00",
        },
    ]
    card = build_forecast_card("Zaqatala", rows)

    assert card is not None
    assert card.budget_estimate == {
        "source": "donor_pipeline_project",
        "total_amount_usd_text": "250,000,000",
        "url": "https://projects.worldbank.org/en/projects-operations/project-detail/P999999",
    }
```

Save as `tests/unit/test_forecast_card.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_forecast_card.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.tender.forecast_card'`.

- [ ] **Step 3: Write `forecast_card.py`**

```python
"""Forecast-card evidence assembly (TENDER_INTELLIGENCE_SPEC.md §5.4,
P311). Pure assembly, no DB, no network -- same shape as
object_intersection.py/signal_model.py.

P311: "карточка собирается только при пороге, содержит проверяемую
цепочку улик" (a card is assembled only at threshold, and contains a
verifiable evidence chain). The real threshold (>=50%, three calibrated
probabilities) is TBD-TIS-02 -- no calibrated model exists yet. This
module substitutes the real, non-fabricated `is_composite` boolean
(object_intersection.py, task 2.C) as an honest stand-in for that
still-missing threshold: `build_forecast_card` returns None exactly when
`detect_intersection(...).is_composite` is False, refusing to assemble a
card at all below that bar -- the same "don't build it below threshold"
intent as P311, just gated on a real fact instead of an uncalibrated
percentage. Recorded as a deliberate deviation in
docs/decisions/OPEN-QUESTIONS.md, not silently presented as satisfying
the spec's literal wording.

Deliberately NOT built here (recorded as open, not invented):
- The spec's three probabilities and publication window -- both need the
  same TBD-TIS-02 calibration the tier work in object_intersection.py
  already deferred.
- Next Best Action -- no source document defines what this text should
  say; inventing one would be exactly the kind of fabrication this
  project's hard bans forbid.
- Delivery (weekly digest / urgent alert) -- a separate future task, not
  part of assembling the card itself.

"оценка бюджета" (budget estimate) is real, not calibrated: it is
whatever monetary field a signal's own source document already carries,
surfaced as-is. Today only `donor_pipeline_project` signals
(signal_model.py's build_donor_pipeline_signal) carry one
(`total_amount_usd_text`, plus `url`) -- design_tender/procurement_plan
signals carry no monetary field at all, so budget_estimate is honestly
None for an object with only those types accumulated.

"цепочка улик... со ссылками" (evidence chain with links): only
donor_pipeline_project signals carry a real clickable `url`.
design_tender/procurement_plan signals carry none (eTender's events-list/
app-list resources don't expose one) -- inventing a guessed URL pattern
would fabricate a fact never actually captured. Every evidence entry
does carry raw_snapshot_id, a real, always-present, verifiable pointer to
its own raw evidence bytes -- used as the honest "link" surrogate where no
real URL exists."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .object_intersection import detect_intersection


@dataclass(frozen=True)
class ForecastCard:
    object_region: str
    is_composite: bool
    signal_types: frozenset[str]
    budget_estimate: dict[str, Any] | None
    evidence_chain: tuple[dict[str, Any], ...]


def build_forecast_card(object_region: str, signal_rows: Sequence[dict[str, Any]]) -> ForecastCard | None:
    intersection = detect_intersection(object_region, signal_rows)
    if not intersection.is_composite:
        return None

    budget_estimate: dict[str, Any] | None = None
    for row in signal_rows:
        if row["signal_type"] == "donor_pipeline_project":
            budget_estimate = {"source": "donor_pipeline_project", **row["value"]}
            break

    evidence_chain = tuple(
        {
            "signal_type": row["signal_type"],
            "source": row["source"],
            "observed_at": row["observed_at"],
            "raw_snapshot_id": row["raw_snapshot_id"],
            "value": row["value"],
        }
        for row in signal_rows
    )

    return ForecastCard(
        object_region=object_region,
        is_composite=True,
        signal_types=intersection.signal_types,
        budget_estimate=budget_estimate,
        evidence_chain=evidence_chain,
    )
```

Save as `packages/tender/forecast_card.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_forecast_card.py -v`
Expected: all three PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/tender/forecast_card.py tests/unit/test_forecast_card.py
git commit -m "feat(tender): pure forecast-card evidence-chain assembler (P311, task 2.D 1/3)"
```

---

## Task 2: `signals_store.build_object_region_forecast_card` — real proof on Zaqatala + Siyəzən

**Files:**
- Modify: `packages/tender/signals_store.py`
- Test: `tests/integration/test_object_region_forecast_card_store.py`

**Interfaces:**
- Consumes: `list_signals_by_object_region` (existing), `ForecastCard`/`build_forecast_card` (Task 1).
- Produces:
  `async def build_object_region_forecast_card(conn: AsyncConnection, *, object_region: str) -> ForecastCard | None`.

- [ ] **Step 1: Write the failing test (real fixtures, no live fetch)**

```python
"""Real proof that `build_object_region_forecast_card` assembles a genuine
evidence-chain card for Zaqatala (composite: design_tender + procurement_plan,
14 real signals, no donor_pipeline_project signal so budget_estimate is
honestly None) and returns None for Siyəzən (non-composite, same real
negative case task 2.C already proved) -- both from fixtures already
committed, no new live fetch needed."""

from __future__ import annotations

import json
from pathlib import Path

from packages.tender.etender_connector import ingest_design_tender_signals_page, ingest_procurement_plan_page
from packages.tender.signals_store import build_object_region_forecast_card

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


async def test_zaqatala_gets_a_real_evidence_chain_card_with_no_budget_estimate(engine):
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
            correlation_id="corr-card-composite-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        await ingest_procurement_plan_page(
            conn,
            raw_body=app_raw,
            payload=app_payload,
            year=2026,
            page_number=1,
            buyer_organization_name="ZAQATALA",
            correlation_id="corr-card-composite-2",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        card = await build_object_region_forecast_card(conn, object_region="Zaqatala")

    assert card is not None
    assert card.object_region == "Zaqatala"
    assert card.is_composite is True
    assert card.signal_types == frozenset({"design_tender", "procurement_plan"})
    assert card.budget_estimate is None
    assert len(card.evidence_chain) == 14
    assert {entry["signal_type"] for entry in card.evidence_chain} == {"design_tender", "procurement_plan"}


async def test_siyezen_gets_no_card(engine):
    design_raw = (FIXTURES / "design_tender_search_page1.raw.json").read_bytes()
    design_payload = json.loads(design_raw)

    async with engine.begin() as conn:
        await ingest_design_tender_signals_page(
            conn,
            raw_body=design_raw,
            payload=design_payload,
            query_params=DESIGN_QUERY_PARAMS,
            correlation_id="corr-card-single-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )

        card = await build_object_region_forecast_card(conn, object_region="Siyəzən")

    assert card is None
```

Save as `tests/integration/test_object_region_forecast_card_store.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/integration/test_object_region_forecast_card_store.py -v` (Docker must be running)
Expected: FAIL with `ImportError: cannot import name 'build_object_region_forecast_card'`.

- [ ] **Step 3: Add `build_object_region_forecast_card` to `signals_store.py`**

Read `packages/tender/signals_store.py` first. Add this import alongside the existing
`from .object_intersection import ObjectIntersection, detect_intersection` line:

```python
from .forecast_card import ForecastCard, build_forecast_card
```

Append this function at the end of the file (after `detect_object_region_intersection`):

```python
async def build_object_region_forecast_card(conn: AsyncConnection, *, object_region: str) -> ForecastCard | None:
    """TENDER_INTELLIGENCE_SPEC.md §5.4 / P311: assembles a forecast card's
    real evidence chain for one object, gated on the same is_composite
    fact detect_object_region_intersection already proves -- see
    forecast_card.py's own docstring for what is and isn't built here."""
    rows = await list_signals_by_object_region(conn, object_region=object_region)
    return build_forecast_card(object_region, rows)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_object_region_forecast_card_store.py -v`
Expected: both PASS.

- [ ] **Step 5: Re-run the full unit + integration suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`
Expected: all previously-passing tests still pass, plus the 3 new unit + 2 new integration tests.

- [ ] **Step 6: Commit**

```bash
git add packages/tender/signals_store.py tests/integration/test_object_region_forecast_card_store.py
git commit -m "feat(tender): real forecast-card proof on Zaqatala vs Siyezen (P311, task 2.D 2/3)"
```

---

## Task 3: WORKLOG, Open Questions, full gate, branch + PR + CI + merge

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

Append to `docs/reports/WORKLOG.md`, matching the existing entries' style (`**Сделано:**`, `**Вывод
полного прогона (Fast+Full gate):**`, `**Дальше:**`, `**Блокеры:**`). Content to include, plainly:

- This closes a deliberately trimmed slice of §5.4: `build_forecast_card`/`build_object_region_forecast_card`
  assemble a real, verifiable evidence chain for an object, gated on `is_composite` (task 2.C) standing
  in for the real (missing) probability threshold. Proven on the real Zaqatala case (14 real signals,
  2 signal_types, `budget_estimate=None` — honest, since no `donor_pipeline_project` signal exists for
  this object) and the real Siyəzən negative case (no card).
- What was deliberately NOT built and why: three calibrated probabilities, a publication-window
  estimate, and Next Best Action (all blocked on `TBD-TIS-02`, no calibrated model exists); delivery
  (weekly digest/alert, a separate future task). `budget_estimate` is real-but-partial: only
  `donor_pipeline_project` signals carry one today. Evidence-chain "links" are real-but-partial too:
  only `donor_pipeline_project` entries carry an actual URL, others carry `raw_snapshot_id` as the
  honest surrogate.
- Files: `packages/tender/forecast_card.py` (new), `packages/tender/signals_store.py` (modified),
  `tests/unit/test_forecast_card.py` (new, 3), `tests/integration/test_object_region_forecast_card_store.py`
  (new, 2).
- Paste the actual `pytest`/`ruff`/`mypy`/`check_v1_untouched.py` output from Step 1 into the
  `**Вывод полного прогона (Fast+Full gate):**` code block — do not fabricate pass counts.

- [ ] **Step 3: Open Questions entry**

Append to `docs/decisions/OPEN-QUESTIONS.md`, same format as existing entries (`**Context:**`,
`**Deviation/assumption:**`, `**Consequence that must not be silently dropped:**`, `**Owner follow-up
needed:**`). Content:

- Context: `TENDER_INTELLIGENCE_SPEC.md` §5.4 (`P311`) specifies a forecast card gated on a ≥50%
  calibrated probability, with three probabilities, a publication window, and Next Best Action. This
  task built only the real evidence-chain assembly, gated on `is_composite` instead.
- Deviation/assumption: `is_composite` (a real, non-fabricated boolean) substitutes for the spec's
  literal probability threshold, because no calibrated model exists (`TBD-TIS-02`) and none should be
  invented. Three probabilities, publication window, and Next Best Action are omitted entirely, not
  stubbed. `budget_estimate` and evidence-chain "links" are real but incomplete — only
  `donor_pipeline_project` signals carry a monetary field or a URL; `design_tender`/`procurement_plan`
  signals carry neither, so those fields are honestly `None`/absent for objects accumulating only those
  types (which is every real object found so far).
- Consequence: a card produced by `build_object_region_forecast_card` is NOT the calibrated forecast
  §5.4 describes — it is a real evidence-chain view gated on a cruder, honest proxy. Any future UI/
  delivery work (§5.4's own "доставка" half, still unbuilt) must not present this card as if it carries
  a real confidence percentage or a real publication-window estimate — neither exists yet.
- Owner follow-up needed: Yes, non-blocking. `TBD-TIS-01`/`TBD-TIS-02` still need the owner's
  research/approval gate before real probabilities/tiers/windows can replace the `is_composite` proxy;
  weekly digest/alert delivery remains a separate, unscoped future task.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(tender): record forecast-card proof, real gaps vs TBD-TIS-01/02 (task 2.D 3/3)"
```

- [ ] **Step 5: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b phase2-task2d-forecast-card
git push -u origin phase2-task2d-forecast-card
gh pr create --base master --head phase2-task2d-forecast-card \
  --title "feat(tender): forecast-card evidence chain (Phase 2, task 2.D, trimmed scope)" \
  --body "Builds the real, non-fabricated slice of TENDER_INTELLIGENCE_SPEC.md §5.4: a verifiable evidence chain for an object, gated on is_composite (task 2.C) standing in for the real (missing) probability threshold. Proven on the real Zaqatala case (14 signals, budget_estimate=None honestly) and the real Siyəzən negative case (no card). Three probabilities, publication window, Next Best Action, and delivery are explicitly NOT built — recorded in docs/decisions/OPEN-QUESTIONS.md, blocked on TBD-TIS-01/02."
```

Poll `gh pr checks <number>` every couple of minutes (do not block synchronously) until both `Fast
gate` and `Full gate` report `pass` — `live-fetch` is expected to `fail` and is not required (see
`docs/decisions/OPEN-QUESTIONS.md`'s `etender.gov.az` entry). Then:

```bash
gh pr merge <number> --rebase --delete-branch
git fetch --prune
git checkout master
git reset --hard origin/master
```

(If there are unrelated uncommitted changes in the working tree at this point, `git stash push -u`
before the reset and `git stash pop` after, same pattern used earlier this session.)

---

## Self-review notes

- **Spec coverage:** §5.4's "цепочка улик" (evidence chain) requirement is directly implemented and
  proven with real data (Tasks 1-2). The probability/window/NBA/delivery portions of §5.4 are explicitly
  out of scope, matching the same TBD-blocked treatment task 2.C already established for tiers/TTL —
  recorded as open, not silently skipped (Task 3).
- **No placeholders:** every test case uses fixtures already committed to the repo or minimal synthetic
  dicts matching task 2.C's own precedent (`test_object_intersection.py`) — no fabricated "real" data
  claiming an overlap that doesn't exist (the donor-pipeline budget case is deliberately a unit test with
  synthetic data, not a fake integration fixture).
- **Type consistency:** `ForecastCard`/`build_forecast_card` (Task 1) are consumed unchanged by
  `build_object_region_forecast_card` (Task 2) with the same field names (`object_region`,
  `is_composite`, `signal_types`, `budget_estimate`, `evidence_chain`) used throughout.
