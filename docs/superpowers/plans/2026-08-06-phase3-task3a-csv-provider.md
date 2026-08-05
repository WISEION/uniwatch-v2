# Phase 3, Task 3.A continuation — CSV provider (second FR-VND-04 provider) Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Satisfy `FR-VND-04`'s "минимум два провайдера в Phase 3" by adding a second
`SupplyProvider`: `CsvProvider`, which parses a vendor-supplied CSV price list into the same
`Vendor`/`Offer` shape `SyntheticProvider` already produces.

**Architecture:** Fix a real design gap first: `SupplyProvider.generate(self, *, seed: int, as_of: str)`
was accidentally shaped around `SyntheticProvider`'s own needs — a CSV parser has no meaningful "seed"
(it isn't generating pseudo-random data, it's parsing given input), so forcing one onto the shared
Protocol would be a dishonest, synthetic-specific leak into a supposedly provider-agnostic contract.
Move `seed` to `SyntheticProvider.__init__`; the shared `generate()` keeps only `as_of` (every provider
needs a reference time, for evidence/validity timestamping). This is the cheapest point to fix it — only
one provider and its own tests depend on the old shape.

**Tech Stack:** Python 3.12 stdlib `csv` module (no new dependency).

## Global Constraints

- **`CsvProvider` still produces `data_realm="vendor-sandbox"`/`watermark="SYNTHETIC"`** — the real
  vendor onboarding legal/privacy/security gate hasn't opened (`ADR-0004`), so *any* provider's output
  stays sandbox-realm regardless of input shape (CSV vs. generated) until that gate does. `FR-VND-04`'s
  "second provider" requirement is about proving the adapter abstraction supports a different input
  shape, not about crossing into real data.
- **The sample CSV used in tests is explicitly a parser-format fixture, not a claim about a real
  vendor's actual prices** — same honest framing as `SyntheticProvider`'s own generated data.
- This is a breaking change to `SupplyProvider`/`SyntheticProvider`'s constructor — both are only
  consumed by this repo's own tests so far (confirmed: `packages/vendor` has no other importer yet),
  so no external caller breaks.
- Every commit lands via a feature branch + PR + green CI.
- Every requirement ID used must trace to `TENDER_INTELLIGENCE_SPEC.md` §6.1, `FR-VND-04`,
  `FR-VND-05` — already-existing IDs.

---

## Task 1: Move `seed` off the shared contract, into `SyntheticProvider`'s own constructor

**Files:**
- Modify: `packages/vendor/provider_contract.py`
- Modify: `packages/vendor/synthetic_provider.py`
- Modify: `tests/unit/test_provider_contract.py`
- Modify: `tests/unit/test_synthetic_provider.py`
- Modify: `tests/integration/test_vendor_store.py`

**Interfaces:**
- Produces: `SupplyProvider.generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]` (no more
  `seed` parameter). `SyntheticProvider(seed: int)` — seed moves to `__init__`.

- [ ] **Step 1: Update the failing/changing tests first**

In `tests/unit/test_provider_contract.py`, change `_FakeProvider.generate` and the call site:

```python
class _FakeProvider:
    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        return [], []


def test_a_conforming_class_satisfies_the_protocol():
    provider: SupplyProvider = _FakeProvider()
    vendors, offers = provider.generate(as_of="2026-08-06T00:00:00+00:00")
    assert vendors == []
    assert offers == []
```

In `tests/unit/test_synthetic_provider.py`, change every call site from
`SyntheticProvider().generate(seed=N, as_of=AS_OF)` to
`SyntheticProvider(seed=N).generate(as_of=AS_OF)` (12 call sites — every test in this file constructs
`SyntheticProvider()` then calls `.generate(...)`; move the `seed=` argument to the constructor call in
each one).

In `tests/integration/test_vendor_store.py`, change both call sites from
`SyntheticProvider().generate(seed=7, as_of=AS_OF)` / `seed=8` to
`SyntheticProvider(seed=7).generate(as_of=AS_OF)` / `SyntheticProvider(seed=8).generate(as_of=AS_OF)`.

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_provider_contract.py tests/unit/test_synthetic_provider.py tests/integration/test_vendor_store.py -v`
Expected: FAIL — `TypeError: generate() got an unexpected keyword argument 'seed'` (current code still
has the old signature).

- [ ] **Step 3: Update `provider_contract.py`**

```python
class SupplyProvider(Protocol):
    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]: ...
```

- [ ] **Step 4: Update `synthetic_provider.py`**

Read the file first. Change the class to take `seed` at construction:

```python
class SyntheticProvider:
    def __init__(self, *, seed: int) -> None:
        self._seed = seed

    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        rng = random.Random(self._seed)
        as_of_dt = datetime.fromisoformat(as_of)
        ...
```

(Replace every remaining use of the old `seed` parameter inside the method body with `self._seed` —
only the `Vendor(..., seed=seed, ...)` construction calls inside `_vendor()` need `self._seed` instead
of `seed`. The rest of the method body is unchanged.)

- [ ] **Step 5: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_provider_contract.py tests/unit/test_synthetic_provider.py tests/integration/test_vendor_store.py -v`
Expected: all PASS.

- [ ] **Step 6: Commit**

```bash
git add packages/vendor/provider_contract.py packages/vendor/synthetic_provider.py tests/unit/test_provider_contract.py tests/unit/test_synthetic_provider.py tests/integration/test_vendor_store.py
git commit -m "refactor(vendor): move seed off the shared provider contract into SyntheticProvider (FR-VND-04 prep)"
```

---

## Task 2: `CsvProvider` — the second `FR-VND-04` provider

**Files:**
- Create: `packages/vendor/csv_provider.py`
- Test: `tests/unit/test_csv_provider.py`

**Interfaces:**
- Consumes: `Vendor`/`Offer` (existing), `SupplyProvider` (Task 1's fixed shape).
- Produces: `class CsvProvider` with `__init__(self, *, csv_content: str)` and
  `generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]`.

- [ ] **Step 1: Write the failing test**

```python
"""Unit tests for CsvProvider (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04's
second required Phase 3 provider). The CSV content here is a parser-format
fixture -- it proves the parsing logic, not a claim about any real
vendor's actual prices (no real vendor CSV exists in this session)."""

from __future__ import annotations

from packages.vendor.csv_provider import CsvProvider

AS_OF = "2026-08-06T00:00:00+00:00"

SAMPLE_CSV = (
    "vendor_name,material,price,currency,vat_rate,uom,uom_canonical_qty,"
    "moq,capacity,inventory,valid_from,valid_until\n"
    "CSV Rebar Co,rebar-16mm,870.50,AZN,18.0,ton,1.0,5,150,90,"
    "2026-08-01T00:00:00+00:00,2026-09-15T00:00:00+00:00\n"
    "CSV Cement Co,cement-42.5,180.00,AZN,18.0,ton,1.0,2,400,250,"
    "2026-08-01T00:00:00+00:00,2026-09-15T00:00:00+00:00\n"
)


def test_parses_every_row_into_a_vendor_and_offer():
    vendors, offers = CsvProvider(csv_content=SAMPLE_CSV).generate(as_of=AS_OF)
    assert len(vendors) == 2
    assert len(offers) == 2
    assert {v.name for v in vendors} == {"CSV Rebar Co", "CSV Cement Co"}
    rebar = next(o for o in offers if o.material == "rebar-16mm")
    assert rebar.price == 870.50
    assert rebar.currency == "AZN"
    assert rebar.vat_rate == 18.0
    assert rebar.uom == "ton"
    assert rebar.moq == 5.0
    assert rebar.capacity == 150.0
    assert rebar.inventory == 90.0
    assert rebar.vendor_name == "CSV Rebar Co"


def test_every_parsed_record_is_sandbox_realm_and_synthetic_watermarked():
    # ADR-0004: the real vendor onboarding gate hasn't opened, so every
    # provider's output stays sandbox/SYNTHETIC regardless of input shape.
    vendors, offers = CsvProvider(csv_content=SAMPLE_CSV).generate(as_of=AS_OF)
    assert all(v.data_realm == "vendor-sandbox" and v.watermark == "SYNTHETIC" for v in vendors)
    assert all(o.data_realm == "vendor-sandbox" and o.watermark == "SYNTHETIC" for o in offers)


def test_evidence_source_and_observed_at_are_set_from_as_of():
    vendors, offers = CsvProvider(csv_content=SAMPLE_CSV).generate(as_of=AS_OF)
    assert all(o.evidence_source == "csv-upload" for o in offers)
    assert all(o.observed_at == AS_OF for o in offers)
    assert all(o.adverse_case is None for o in offers)


def test_empty_csv_content_produces_no_records():
    header_only = (
        "vendor_name,material,price,currency,vat_rate,uom,uom_canonical_qty,moq,capacity,inventory,valid_from,valid_until\n"
    )
    vendors, offers = CsvProvider(csv_content=header_only).generate(as_of=AS_OF)
    assert vendors == []
    assert offers == []


def test_missing_required_column_raises_a_typed_error():
    from packages.vendor.csv_provider import CsvParseError

    malformed_csv = "vendor_name,material,price\nX,Y,1.0\n"
    with pytest.raises(CsvParseError):
        CsvProvider(csv_content=malformed_csv).generate(as_of=AS_OF)
```

Add `import pytest` at the top of the file alongside the existing imports. Save as
`tests/unit/test_csv_provider.py`.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/unit/test_csv_provider.py -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'packages.vendor.csv_provider'`.

- [ ] **Step 3: Write `csv_provider.py`**

```python
"""CSV provider (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04's second
required Phase 3 provider): parses a vendor-supplied CSV price list into
the same Vendor/Offer shape SyntheticProvider produces, proving the
provider-adapter abstraction supports a genuinely different input shape
(a given file, not a pseudo-random generator) -- not a claim about any
real vendor's actual data. Still data_realm="vendor-sandbox"/
watermark="SYNTHETIC": the real vendor onboarding legal/privacy/security
gate hasn't opened (ADR-0004), so every provider's output stays
sandbox-realm regardless of input shape until that gate does."""

from __future__ import annotations

import csv
import io

from .vendor_model import Offer, Vendor

REQUIRED_COLUMNS = (
    "vendor_name",
    "material",
    "price",
    "currency",
    "vat_rate",
    "uom",
    "uom_canonical_qty",
    "moq",
    "capacity",
    "inventory",
    "valid_from",
    "valid_until",
)


class CsvParseError(Exception):
    """The given CSV content is missing a required column, or a row's
    value can't be parsed into the expected type -- always this one typed
    error, never a bare csv/ValueError leaking to the caller."""


class CsvProvider:
    def __init__(self, *, csv_content: str) -> None:
        self._csv_content = csv_content

    def generate(self, *, as_of: str) -> tuple[list[Vendor], list[Offer]]:
        reader = csv.DictReader(io.StringIO(self._csv_content))
        if reader.fieldnames is None:
            return [], []
        missing = [col for col in REQUIRED_COLUMNS if col not in reader.fieldnames]
        if missing:
            raise CsvParseError(f"CSV is missing required column(s): {', '.join(missing)}")

        vendors: list[Vendor] = []
        offers: list[Offer] = []
        for row in reader:
            vendor = Vendor(
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                name=row["vendor_name"],
                provider_type="csv",
                seed=None,
            )
            vendors.append(vendor)
            try:
                offers.append(
                    Offer(
                        vendor_name=row["vendor_name"],
                        data_realm="vendor-sandbox",
                        watermark="SYNTHETIC",
                        material=row["material"],
                        price=float(row["price"]),
                        currency=row["currency"],
                        vat_rate=float(row["vat_rate"]),
                        uom=row["uom"],
                        uom_canonical_qty=float(row["uom_canonical_qty"]),
                        moq=float(row["moq"]),
                        capacity=float(row["capacity"]),
                        inventory=float(row["inventory"]),
                        valid_from=row["valid_from"],
                        valid_until=row["valid_until"],
                        evidence_source="csv-upload",
                        observed_at=as_of,
                        adverse_case=None,
                    )
                )
            except ValueError as exc:
                raise CsvParseError(f"CSV row for vendor {row['vendor_name']!r} has an invalid value: {exc}") from exc

        return vendors, offers
```

Save as `packages/vendor/csv_provider.py`.

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/unit/test_csv_provider.py -v`
Expected: all 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/csv_provider.py tests/unit/test_csv_provider.py
git commit -m "feat(vendor): CSV provider, second FR-VND-04 provider for Phase 3"
```

---

## Task 3: WORKLOG, Open Questions, full gate, branch + PR + CI + merge

**Files:**
- Modify: `docs/reports/WORKLOG.md`
- Modify: `docs/decisions/OPEN-QUESTIONS.md`

- [ ] **Step 1: Run the full gate**

```bash
python -m pytest tests/ -q
python -m ruff format --check . && python -m ruff check . && python -m mypy packages apps && python tools/check_v1_untouched.py
```

- [ ] **Step 2: WORKLOG entry**

State: `SupplyProvider`'s contract fixed (seed moved off the shared interface into
`SyntheticProvider.__init__`, since a CSV parser has no meaningful seed); `CsvProvider` added, `FR-VND-04`'s
"minimum two providers in Phase 3" now satisfied; both providers still sandbox-realm/SYNTHETIC per
`ADR-0004` (real onboarding gate not open). Paste real gate output.

- [ ] **Step 3: Open Questions entry**

Record: `FR-VND-04` is now satisfied (2 providers: synthetic, CSV). `CsvProvider`'s CSV schema
(the 12 columns above) is this task's own invention, not dictated by any real vendor's actual export
format — when a real vendor CSV is eventually available, its actual column names/shape may differ and
`CsvProvider` may need adjusting, not assumed to already match. `FR-VND-09` route/service isolation and
the "handled by an explicit decision" half of `FR-VND-03` remain open from prior entries, unaffected.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(vendor): record CSV provider, FR-VND-04 satisfied (2 providers)"
```

- [ ] **Step 5: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b phase3-task3a-csv-provider
git push -u origin phase3-task3a-csv-provider
gh pr create --base master --head phase3-task3a-csv-provider \
  --title "feat(vendor): CSV provider, FR-VND-04's second Phase 3 provider" \
  --body "Fixes SupplyProvider's contract (seed moved off the shared interface into SyntheticProvider.__init__ -- a CSV parser has no meaningful seed) and adds CsvProvider, satisfying FR-VND-04's 'minimum two providers in Phase 3'. Both providers still produce data_realm=vendor-sandbox/watermark=SYNTHETIC (ADR-0004: real onboarding gate not open). The CSV schema used is this task's own invention, not a real vendor's actual export format -- recorded in docs/decisions/OPEN-QUESTIONS.md."
```

Poll `gh pr checks <number>` until Fast gate + Full gate both `pass`. Then
`gh pr merge <number> --rebase --delete-branch`, then `git fetch --prune`, `git checkout master`,
`git reset --hard origin/master` (stash/pop any unrelated uncommitted work first).

---

## Self-review notes

- **Spec coverage:** `FR-VND-04`'s "one adapter contract, ≥2 providers in Phase 3" is now fully real —
  the contract fix makes the abstraction honest for a non-generator provider, not just a cosmetic Protocol.
- **No placeholders:** `CsvProvider`'s parsing, error path, and every field mapping are concrete.
- **Type consistency:** `SupplyProvider.generate(*, as_of)` (Task 1) is the exact shape both
  `SyntheticProvider` and `CsvProvider` (Task 2) implement.
