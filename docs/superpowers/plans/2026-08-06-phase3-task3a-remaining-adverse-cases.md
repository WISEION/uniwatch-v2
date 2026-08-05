# Phase 3, Task 3.A continuation — remaining 5 adverse cases Implementation Plan

> **For agentic workers:** this plan is executed inline, in the same session that wrote it — this
> repo's established convention. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Extend `packages/vendor/synthetic_provider.py` to cover the remaining 5 of `FR-VND-03`'s 7
named adverse cases (`mixed_uom`, `currency_vat_mismatch`, `capacity_shortfall`, `expiring_evidence`,
`partial_fulfillment`) — the first slice (task 3.A) already covers `stale_offer`/`moq_conflict`.

**Architecture:** Each new case is one more `Vendor`/`Offer` pair appended to
`SyntheticProvider.generate()`'s existing deterministic sequence, each with exactly one adverse
property deliberately set (everything else normal), so each case is isolated and unambiguous to test —
same shape as the two cases already built.

**Tech Stack:** Python 3.12, no new dependencies.

## Global Constraints

- Each new case's own concrete definition (below) is a generator-internal business rule for producing a
  labeled representative example — not a `TBD-nn` calibrated forecast number, so defining a concrete
  threshold (e.g. "inventory < capacity × 0.5") here does not violate the never-invent-a-TBD-number ban.
- **`FR-VND-03`'s acceptance criterion is "каждый случай представлен и обрабатывается решением явно"**
  (each case is represented AND handled by an explicit decision). This task only builds the
  **representation** half — the generator producing a labeled example of each case. No downstream code
  yet "decides" anything in response to an `adverse_case` label (that's task 3.C/3.D, matching/
  availability logic, later work). Record this precisely in `docs/decisions/OPEN-QUESTIONS.md`, don't
  overclaim `FR-VND-03` as fully satisfied.
- Every requirement ID used must trace to `TENDER_INTELLIGENCE_SPEC.md` §6.1, `FR-VND-03`, `P312` —
  already-existing IDs, do not invent a new one.
- Every commit lands via a feature branch + PR + green CI, not a direct push to `master`.

---

## Task 1: Add the 5 remaining adverse cases to `synthetic_provider.py`

**Files:**
- Modify: `packages/vendor/synthetic_provider.py`
- Modify: `tests/unit/test_synthetic_provider.py`

**Interfaces:**
- `SyntheticProvider.generate()`'s return shape is unchanged (`tuple[list[Vendor], list[Offer]]`) — it
  now returns 8 vendors / 8 offers instead of 3 (1 normal + 7 adverse cases, one offer each).

- [ ] **Step 1: Write the 5 failing tests**

Append to `tests/unit/test_synthetic_provider.py`:

```python
def test_covers_mixed_uom_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    mixed = next(o for o in offers if o.adverse_case == "mixed_uom")
    # Quoted in a non-canonical unit (kg, not the material's canonical ton)
    # -- uom_canonical_qty is a real conversion factor, not 1.0.
    assert mixed.uom == "kg"
    assert mixed.uom_canonical_qty != 1.0


def test_covers_currency_vat_mismatch_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    mismatch = next(o for o in offers if o.adverse_case == "currency_vat_mismatch")
    assert mismatch.currency != "AZN"
    assert mismatch.vat_rate != 18.0


def test_covers_capacity_shortfall_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    shortfall = next(o for o in offers if o.adverse_case == "capacity_shortfall")
    # On-hand inventory exceeds ongoing supply capacity -- once depleted,
    # replenishment lags behind (a real forward-looking constraint).
    assert shortfall.inventory > shortfall.capacity


def test_covers_expiring_evidence_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    expiring = next(o for o in offers if o.adverse_case == "expiring_evidence")
    as_of_dt = datetime.fromisoformat(AS_OF)
    observed_at_dt = datetime.fromisoformat(expiring.observed_at)
    # Still formally valid (unlike stale_offer)...
    assert datetime.fromisoformat(expiring.valid_until) > as_of_dt
    # ...but the evidence itself is more than 20 days old and should be re-verified.
    assert (as_of_dt - observed_at_dt).days > 20


def test_covers_partial_fulfillment_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    partial = next(o for o in offers if o.adverse_case == "partial_fulfillment")
    # On-hand inventory covers less than half of stated capacity.
    assert partial.inventory < partial.capacity * 0.5


def test_generates_exactly_one_normal_and_seven_distinct_adverse_offers():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    assert len(offers) == 8
    adverse_cases = {o.adverse_case for o in offers}
    assert adverse_cases == {
        None,
        "stale_offer",
        "moq_conflict",
        "mixed_uom",
        "currency_vat_mismatch",
        "capacity_shortfall",
        "expiring_evidence",
        "partial_fulfillment",
    }
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/unit/test_synthetic_provider.py -v`
Expected: the 6 new tests FAIL (`StopIteration` from `next(...)` finding no matching offer, or the
count assertion failing) — the 6 pre-existing tests still PASS.

- [ ] **Step 3: Add the 5 new cases to `SyntheticProvider.generate()`**

Read `packages/vendor/synthetic_provider.py` first. Update its module docstring's "Covers 2 of
FR-VND-03's 7..." paragraph to say "Covers all 7 of FR-VND-03's named adverse cases" and remove the
now-stale "remaining 5... future work" sentence. Then, right before the final `return vendors, offers`
line, insert:

```python
        # Adverse case: mixed_uom -- quoted in a non-canonical unit (kg,
        # not this material's canonical ton), a real conversion factor
        # instead of 1.0.
        mixed_uom_vendor = _vendor("Synthetic Rebar Supplier (mixed uom)")
        offers.append(
            Offer(
                vendor_name=mixed_uom_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="rebar-12mm",
                price=round(rng.uniform(0.8, 0.9), 4),
                currency="AZN",
                vat_rate=18.0,
                uom="kg",
                uom_canonical_qty=0.001,
                moq=5000.0,
                capacity=200000.0,
                inventory=150000.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="mixed_uom",
            )
        )

        # Adverse case: currency_vat_mismatch -- quoted in a foreign
        # currency with a non-standard VAT rate; downstream costing
        # (task 3.D's TCO) must not silently assume AZN/18% for every offer.
        currency_vat_vendor = _vendor("Synthetic Import Cement Supplier (currency/VAT mismatch)")
        offers.append(
            Offer(
                vendor_name=currency_vat_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="cement-imported-52.5",
                price=round(rng.uniform(60.0, 80.0), 2),
                currency="USD",
                vat_rate=0.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=10.0,
                capacity=1000.0,
                inventory=600.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="currency_vat_mismatch",
            )
        )

        # Adverse case: capacity_shortfall -- on-hand inventory exceeds
        # ongoing supply capacity; once this stock sells, replenishment
        # lags behind (a real forward-looking supply constraint, distinct
        # from moq_conflict's own moq > capacity self-contradiction).
        capacity_shortfall_vendor = _vendor("Synthetic Steel Supplier (capacity shortfall)")
        offers.append(
            Offer(
                vendor_name=capacity_shortfall_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="steel-beam-ipe200",
                price=round(rng.uniform(900.0, 1000.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="ton",
                uom_canonical_qty=1.0,
                moq=10.0,
                capacity=50.0,
                inventory=120.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="capacity_shortfall",
            )
        )

        # Adverse case: expiring_evidence -- still formally valid
        # (valid_until in the future, unlike stale_offer) but the evidence
        # itself (observed_at) is more than 20 days old and should be
        # re-verified (INV-15/17-style TTL freshness concern).
        expiring_evidence_vendor = _vendor("Synthetic Timber Supplier (expiring evidence)")
        offers.append(
            Offer(
                vendor_name=expiring_evidence_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="timber-formwork-18mm",
                price=round(rng.uniform(15.0, 25.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="m2",
                uom_canonical_qty=1.0,
                moq=50.0,
                capacity=2000.0,
                inventory=1200.0,
                valid_from=(as_of_dt - timedelta(days=45)).isoformat(),
                valid_until=(as_of_dt + timedelta(days=10)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=(as_of_dt - timedelta(days=25)).isoformat(),
                adverse_case="expiring_evidence",
            )
        )

        # Adverse case: partial_fulfillment -- on-hand inventory covers
        # less than half of stated capacity; the vendor could theoretically
        # produce up to `capacity`, but current stock could only partially
        # fulfill an order sized at capacity.
        partial_vendor = _vendor("Synthetic Pipe Supplier (partial fulfillment)")
        offers.append(
            Offer(
                vendor_name=partial_vendor.name,
                data_realm="vendor-sandbox",
                watermark="SYNTHETIC",
                material="hdpe-pipe-110mm",
                price=round(rng.uniform(20.0, 30.0), 2),
                currency="AZN",
                vat_rate=18.0,
                uom="m",
                uom_canonical_qty=1.0,
                moq=100.0,
                capacity=300.0,
                inventory=80.0,
                valid_from=as_of_dt.isoformat(),
                valid_until=(as_of_dt + timedelta(days=30)).isoformat(),
                evidence_source="synthetic-generator",
                observed_at=as_of,
                adverse_case="partial_fulfillment",
            )
        )
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/unit/test_synthetic_provider.py -v`
Expected: all 12 tests PASS.

- [ ] **Step 5: Commit**

```bash
git add packages/vendor/synthetic_provider.py tests/unit/test_synthetic_provider.py
git commit -m "feat(vendor): remaining 5 adverse cases in synthetic provider (FR-VND-03, 7/7)"
```

---

## Task 2: Update the real DB round-trip test for the new offer count

**Files:**
- Modify: `tests/integration/test_vendor_store.py`

**Interfaces:**
- Consumes: `SyntheticProvider` (Task 1's updated `generate()`, now returns 8 vendors/8 offers).

- [ ] **Step 1: Update the existing assertions**

Read `tests/integration/test_vendor_store.py` first. In
`test_synthetic_generation_round_trips_through_the_database`, change:

```python
    assert len(rows) == 3
    assert all(row["watermark"] == "SYNTHETIC" for row in rows)
    assert {row["adverse_case"] for row in rows} == {None, "stale_offer", "moq_conflict"}
```

to:

```python
    assert len(rows) == 8
    assert all(row["watermark"] == "SYNTHETIC" for row in rows)
    assert {row["adverse_case"] for row in rows} == {
        None,
        "stale_offer",
        "moq_conflict",
        "mixed_uom",
        "currency_vat_mismatch",
        "capacity_shortfall",
        "expiring_evidence",
        "partial_fulfillment",
    }
```

Leave the rest of the test (including the `stale_row` assertion right after) unchanged.

- [ ] **Step 2: Run test to verify it passes**

Run: `python -m pytest tests/integration/test_vendor_store.py -v`
Expected: both tests PASS.

- [ ] **Step 3: Re-run the full unit + integration suite to confirm nothing else broke**

Run: `python -m pytest tests/ -q`

- [ ] **Step 4: Commit**

```bash
git add tests/integration/test_vendor_store.py
git commit -m "test(vendor): update round-trip proof for all 7 adverse cases"
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

Append to `docs/reports/WORKLOG.md` (`**Сделано:**`/`**Вывод полного прогона...**`/`**Дальше:**`/
`**Блокеры:**`). State: all 7 of `FR-VND-03`'s named adverse cases are now represented by
`SyntheticProvider` (up from 2); paste real gate output; note that "represented" ≠ "handled by an
explicit decision" (the other half of `FR-VND-03`'s acceptance criterion) — nothing downstream
consumes `adverse_case` yet, that's task 3.C/3.D.

- [ ] **Step 3: Open Questions entry**

Append to `docs/decisions/OPEN-QUESTIONS.md`. Record: `FR-VND-03`'s "represented" half is now fully
done (7/7), but its "handled by an explicit decision" half is not — no matching/availability logic
(tasks 3.C/3.D) exists yet to react to an `adverse_case` label. `FR-VND-04`'s second-provider
requirement and `FR-VND-09`'s route/service isolation remain open from task 3.A's own prior entry,
unaffected by this task.

- [ ] **Step 4: Commit the docs**

```bash
git add docs/reports/WORKLOG.md docs/decisions/OPEN-QUESTIONS.md
git commit -m "docs(vendor): record all 7 adverse cases represented, decision-handling still open"
```

- [ ] **Step 5: Push a branch, open a PR, wait for CI, merge**

```bash
git checkout -b phase3-task3a-remaining-adverse-cases
git push -u origin phase3-task3a-remaining-adverse-cases
gh pr create --base master --head phase3-task3a-remaining-adverse-cases \
  --title "feat(vendor): remaining 5 adverse cases, all 7/7 represented (FR-VND-03)" \
  --body "Extends SyntheticProvider with mixed_uom, currency_vat_mismatch, capacity_shortfall, expiring_evidence, and partial_fulfillment -- all 7 of FR-VND-03's named adverse cases are now represented. Recorded in docs/decisions/OPEN-QUESTIONS.md: 'represented' is done, 'handled by an explicit decision' (the rest of FR-VND-03's acceptance criterion) needs task 3.C/3.D matching logic, not yet built."
```

Poll `gh pr checks <number>` until Fast gate + Full gate both `pass` (`live-fetch` expected `fail`, not
required). Then `gh pr merge <number> --rebase --delete-branch`, then `git fetch --prune`,
`git checkout master`, `git reset --hard origin/master` (stash/pop any unrelated uncommitted work first).

---

## Self-review notes

- **Spec coverage:** all 7 of `FR-VND-03`'s named cases now map to a concrete offer in the generator.
- **No placeholders:** each new case has a concrete, defensible numeric definition, not "add more cases
  later" left vague.
- **Type consistency:** no changes to `Vendor`/`Offer`/`SupplyProvider` shapes — only new instances.
