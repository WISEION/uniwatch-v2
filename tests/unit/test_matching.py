"""Unit tests for packages/decision/matching.py (task 3.D,
TENDER_INTELLIGENCE_SPEC.md §6.4, P315): inverted matching -- executability
(source count, freshness, volume, raw reputation presence) before price.
Pure functions, no DB -- VendorOfferDTO stands in for a real
packages/contracts response."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from packages.contracts.vendor_api import VendorOfferDTO
from packages.decision.matching import classify_candidate, match_boq_line
from packages.tender.boq_line_model import BoqLine


def _boq_line(
    *,
    qty: str = "10",
    unit_canonical: str | None = "t",
    unit_status: str = "mapped",
    description: str = "cement M400 for foundation",
) -> BoqLine:
    return BoqLine(
        source_line_id=1,
        page_number=1,
        section=None,
        category_code=None,
        description=description,
        unit_raw="t",
        unit_canonical=unit_canonical,
        unit_status=unit_status,
        qty=Decimal(qty),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("120"),
        amount=Decimal("1200"),
    )


def _offer(
    *,
    vendor_id: int = 1,
    vendor_name: str = "Vendor A",
    material: str = "cement M400",
    inventory: float = 40.0,
    uom: str = "t",
    valid_until: str = "2026-09-01T00:00:00+00:00",
    has_positive_reputation: bool = False,
    has_negative_reputation: bool = False,
    price: float = 120.0,
    vat_rate: float = 0.18,
) -> VendorOfferDTO:
    return VendorOfferDTO(
        id=1,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material=material,
        price=price,
        currency="AZN",
        vat_rate=vat_rate,
        uom=uom,
        uom_canonical_qty=1.0,
        moq=1.0,
        capacity=100.0,
        inventory=inventory,
        valid_from="2026-08-01T00:00:00+00:00",
        valid_until=valid_until,
        evidence_source="test",
        observed_at="2026-08-01T00:00:00+00:00",
        adverse_case=None,
        has_positive_reputation=has_positive_reputation,
        has_negative_reputation=has_negative_reputation,
    )


AS_OF = datetime.fromisoformat("2026-08-06T00:00:00+00:00")


def test_classify_candidate_flags_fresh_and_sufficient_volume():
    boq_line = _boq_line(qty="10")
    offer = _offer(inventory=40.0)

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.freshness == "fresh"
    assert candidate.volume_status == "sufficient"


def test_classify_candidate_flags_stale_when_as_of_past_valid_until():
    boq_line = _boq_line()
    offer = _offer(valid_until="2026-08-05T00:00:00+00:00")

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.freshness == "stale"


def test_classify_candidate_flags_insufficient_volume():
    boq_line = _boq_line(qty="100")
    offer = _offer(inventory=10.0)

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.volume_status == "insufficient"


def test_classify_candidate_flags_unit_mismatch():
    boq_line = _boq_line(unit_canonical="kg")
    offer = _offer(uom="t")

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.volume_status == "unit_mismatch"


def test_classify_candidate_flags_unit_unmapped_when_boq_line_unit_unresolved():
    boq_line = _boq_line(unit_canonical=None, unit_status="unmapped")
    offer = _offer()

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.volume_status == "unit_unmapped"


def test_match_boq_line_is_red_with_no_matching_offers():
    boq_line = _boq_line(description="excavation works")
    offers = [_offer(material="cement M400")]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "red"
    assert match.candidates == ()


def test_match_boq_line_is_yellow_with_a_single_source():
    boq_line = _boq_line()
    offers = [_offer(vendor_id=1, has_positive_reputation=True)]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"


def test_match_boq_line_is_yellow_when_two_sources_have_no_positive_history():
    # P315: "две цены от незнакомцев дают 🟡" -- two strangers' prices give yellow.
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A"),
        _offer(vendor_id=2, vendor_name="Vendor B"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"


def test_match_boq_line_is_green_with_two_sources_one_with_positive_history():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True),
        _offer(vendor_id=2, vendor_name="Vendor B"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "green"


def test_match_boq_line_downgrades_to_yellow_when_all_sources_are_stale():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True, valid_until="2026-08-01T00:00:00+00:00"),
        _offer(vendor_id=2, vendor_name="Vendor B", valid_until="2026-08-01T00:00:00+00:00"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"


def test_match_boq_line_excludes_insufficient_volume_offers_from_source_count():
    boq_line = _boq_line(qty="100")
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", inventory=5.0, has_positive_reputation=True),
        _offer(vendor_id=2, vendor_name="Vendor B", inventory=5.0),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "red"


def test_match_boq_line_ranks_executable_candidates_by_price():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", price=150.0, has_positive_reputation=True),
        _offer(vendor_id=2, vendor_name="Vendor B", price=100.0),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    prices = [estimate.base_price_with_vat for _candidate, estimate in match.ranked_executable]
    assert prices == sorted(prices)
    assert all(estimate.status == "partial_price_only" for _candidate, estimate in match.ranked_executable)
    assert len(match.ranked_executable) == 2
    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor B", "Vendor A"]


def test_match_boq_line_ranked_executable_excludes_stale_candidates_even_if_cheaper():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", price=50.0, valid_until="2026-08-01T00:00:00+00:00"),
        _offer(vendor_id=2, vendor_name="Vendor B", price=200.0, has_positive_reputation=True),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor B"]


def test_match_boq_line_is_yellow_not_green_when_units_cannot_be_compared():
    boq_line = _boq_line(unit_canonical="kg")
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", uom="t", has_positive_reputation=True),
        _offer(vendor_id=2, vendor_name="Vendor B", uom="t"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"


def test_match_boq_line_is_yellow_when_only_one_source_is_both_fresh_and_positive():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True, valid_until="2026-08-01T00:00:00+00:00"),
        _offer(vendor_id=2, vendor_name="Vendor B", has_positive_reputation=False),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"


def test_match_boq_line_dedupes_duplicate_vendor_id_when_counting_sources():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True),
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"
