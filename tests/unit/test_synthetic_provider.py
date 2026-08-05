"""Unit tests for the deterministic synthetic supply-side generator
(TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-01, FR-VND-02, FR-VND-03, P312)."""

from datetime import datetime

from packages.vendor.synthetic_provider import SyntheticProvider

AS_OF = "2026-08-06T00:00:00+00:00"


def test_every_generated_record_is_sandbox_realm_and_synthetic_watermarked():
    vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    assert vendors
    assert offers
    assert all(v.data_realm == "vendor-sandbox" and v.watermark == "SYNTHETIC" for v in vendors)
    assert all(o.data_realm == "vendor-sandbox" and o.watermark == "SYNTHETIC" for o in offers)


def test_same_seed_and_as_of_produce_identical_output():
    result_a = SyntheticProvider(seed=42).generate(as_of=AS_OF)
    result_b = SyntheticProvider(seed=42).generate(as_of=AS_OF)
    assert result_a == result_b


def test_different_seed_produces_different_price():
    _vendors_a, offers_a = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    _vendors_b, offers_b = SyntheticProvider(seed=2).generate(as_of=AS_OF)
    normal_a = next(o for o in offers_a if o.adverse_case is None)
    normal_b = next(o for o in offers_b if o.adverse_case is None)
    assert normal_a.price != normal_b.price


def test_covers_stale_offer_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    stale = next(o for o in offers if o.adverse_case == "stale_offer")
    as_of_dt = datetime.fromisoformat(AS_OF)
    valid_until_dt = datetime.fromisoformat(stale.valid_until)
    assert valid_until_dt < as_of_dt


def test_covers_moq_conflict_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    conflict = next(o for o in offers if o.adverse_case == "moq_conflict")
    assert conflict.moq > conflict.capacity


def test_normal_offer_has_no_adverse_case_and_is_not_stale_or_conflicted():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    normal = next(o for o in offers if o.adverse_case is None)
    as_of_dt = datetime.fromisoformat(AS_OF)
    assert datetime.fromisoformat(normal.valid_until) >= as_of_dt
    assert normal.moq <= normal.capacity


def test_covers_mixed_uom_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    mixed = next(o for o in offers if o.adverse_case == "mixed_uom")
    # Quoted in a non-canonical unit (kg, not the material's canonical ton)
    # -- uom_canonical_qty is a real conversion factor, not 1.0.
    assert mixed.uom == "kg"
    assert mixed.uom_canonical_qty != 1.0


def test_covers_currency_vat_mismatch_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    mismatch = next(o for o in offers if o.adverse_case == "currency_vat_mismatch")
    assert mismatch.currency != "AZN"
    assert mismatch.vat_rate != 18.0


def test_covers_capacity_shortfall_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    shortfall = next(o for o in offers if o.adverse_case == "capacity_shortfall")
    # On-hand inventory exceeds ongoing supply capacity -- once depleted,
    # replenishment lags behind (a real forward-looking constraint).
    assert shortfall.inventory > shortfall.capacity


def test_covers_expiring_evidence_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    expiring = next(o for o in offers if o.adverse_case == "expiring_evidence")
    as_of_dt = datetime.fromisoformat(AS_OF)
    observed_at_dt = datetime.fromisoformat(expiring.observed_at)
    # Still formally valid (unlike stale_offer)...
    assert datetime.fromisoformat(expiring.valid_until) > as_of_dt
    # ...but the evidence itself is more than 20 days old and should be re-verified.
    assert (as_of_dt - observed_at_dt).days > 20


def test_covers_partial_fulfillment_adverse_case():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    partial = next(o for o in offers if o.adverse_case == "partial_fulfillment")
    # On-hand inventory covers less than half of stated capacity.
    assert partial.inventory < partial.capacity * 0.5


def test_generates_exactly_one_normal_and_seven_distinct_adverse_offers():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
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
