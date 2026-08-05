"""Unit tests for the deterministic synthetic supply-side generator
(TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-01, FR-VND-02, FR-VND-03, P312)."""

from datetime import datetime

from packages.vendor.synthetic_provider import SyntheticProvider

AS_OF = "2026-08-06T00:00:00+00:00"


def test_every_generated_record_is_sandbox_realm_and_synthetic_watermarked():
    vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    assert vendors
    assert offers
    assert all(v.data_realm == "vendor-sandbox" and v.watermark == "SYNTHETIC" for v in vendors)
    assert all(o.data_realm == "vendor-sandbox" and o.watermark == "SYNTHETIC" for o in offers)


def test_same_seed_and_as_of_produce_identical_output():
    result_a = SyntheticProvider().generate(seed=42, as_of=AS_OF)
    result_b = SyntheticProvider().generate(seed=42, as_of=AS_OF)
    assert result_a == result_b


def test_different_seed_produces_different_price():
    _vendors_a, offers_a = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    _vendors_b, offers_b = SyntheticProvider().generate(seed=2, as_of=AS_OF)
    normal_a = next(o for o in offers_a if o.adverse_case is None)
    normal_b = next(o for o in offers_b if o.adverse_case is None)
    assert normal_a.price != normal_b.price


def test_covers_stale_offer_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    stale = next(o for o in offers if o.adverse_case == "stale_offer")
    as_of_dt = datetime.fromisoformat(AS_OF)
    valid_until_dt = datetime.fromisoformat(stale.valid_until)
    assert valid_until_dt < as_of_dt


def test_covers_moq_conflict_adverse_case():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    conflict = next(o for o in offers if o.adverse_case == "moq_conflict")
    assert conflict.moq > conflict.capacity


def test_normal_offer_has_no_adverse_case_and_is_not_stale_or_conflicted():
    _vendors, offers = SyntheticProvider().generate(seed=1, as_of=AS_OF)
    normal = next(o for o in offers if o.adverse_case is None)
    as_of_dt = datetime.fromisoformat(AS_OF)
    assert datetime.fromisoformat(normal.valid_until) >= as_of_dt
    assert normal.moq <= normal.capacity
