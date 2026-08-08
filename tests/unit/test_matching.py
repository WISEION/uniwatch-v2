"""Unit tests for packages/decision/matching.py (task 3.D,
TENDER_INTELLIGENCE_SPEC.md §6.4, P315, extended by task 3.C's Executable
Availability, §6.3/INV-19/P314): inverted matching -- executability
(source count, freshness, volume, executable status, raw reputation
presence) before price. Pure functions, no DB -- VendorOfferDTO stands in
for a real packages/contracts response. `_offer()`'s `executable_status`
default ("confirmed") keeps every pre-existing test's offers "strong" under
the new gate without having to touch each test individually -- only tests
that exercise the gate itself override it."""

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
    moq: float = 1.0,
    uom: str = "t",
    valid_until: str = "2026-09-01T00:00:00+00:00",
    has_positive_reputation: bool = False,
    has_negative_reputation: bool = False,
    price: float = 120.0,
    vat_rate: float = 18.0,
    currency: str = "AZN",
    executable_status: str = "confirmed",
    effective_executable_status: str | None = None,
) -> VendorOfferDTO:
    return VendorOfferDTO(
        id=1,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material=material,
        price=price,
        currency=currency,
        vat_rate=vat_rate,
        uom=uom,
        uom_canonical_qty=1.0,
        moq=moq,
        capacity=100.0,
        inventory=inventory,
        valid_from="2026-08-01T00:00:00+00:00",
        valid_until=valid_until,
        evidence_source="test",
        observed_at="2026-08-01T00:00:00+00:00",
        adverse_case=None,
        executable_status=executable_status,
        effective_executable_status=effective_executable_status or executable_status,
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


def test_moq_exceeds_qty_is_flagged_but_does_not_change_volume_status_or_traffic_light():
    # A vendor whose MOQ (100) is well above the BOQ line's qty (10) --
    # visible fact, not an executability block (no source document
    # confirms MOQ should gate executability).
    boq_line = _boq_line(qty="10")
    offer = _offer(inventory=40.0, moq=100.0)

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.moq_exceeds_qty is True
    assert candidate.volume_status == "sufficient"

    match = match_boq_line(boq_line, [offer], as_of=AS_OF)
    assert match.traffic_light != "red"
    assert any(c.moq_exceeds_qty for c in match.candidates)


def test_moq_within_qty_is_not_flagged():
    boq_line = _boq_line(qty="10")
    offer = _offer(inventory=40.0, moq=5.0)

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.moq_exceeds_qty is False


def test_moq_exceeds_qty_is_false_when_units_are_not_comparable():
    boq_line = _boq_line(qty="10", unit_status="unmapped", unit_canonical=None)
    offer = _offer(inventory=40.0, moq=100.0)

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.moq_exceeds_qty is False


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


def test_classify_candidate_flags_adverse_case_offers():
    boq_line = _boq_line()
    offer = _offer()
    offer_with_adverse_case = offer.model_copy(update={"adverse_case": "moq_conflict"})

    candidate = classify_candidate(boq_line, offer_with_adverse_case, as_of=AS_OF)

    assert candidate.volume_status == "adverse_case"
    assert candidate.adverse_case == "moq_conflict"


def test_classify_candidate_adverse_case_is_none_for_a_clean_offer():
    boq_line = _boq_line()
    offer = _offer()

    candidate = classify_candidate(boq_line, offer, as_of=AS_OF)

    assert candidate.adverse_case is None


def test_match_boq_line_never_reaches_green_or_ranked_when_source_has_adverse_case():
    boq_line = _boq_line()
    offer = _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True)
    offer_with_adverse_case = offer.model_copy(update={"adverse_case": "capacity_shortfall"})
    offers = [
        offer_with_adverse_case,
        _offer(vendor_id=2, vendor_name="Vendor B", has_positive_reputation=True),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    # Yellow, not green: the adverse-case offer still counts as "a source
    # exists" (so not red) but never as a *confirmed* one, so only one
    # vendor is confirmed-fresh-and-sufficient. The adverse-case Vendor A is
    # likewise absent from ranked_executable; the clean Vendor B is the only
    # entry (excluding a clean co-candidate too would be wrong -- the
    # exclusion is per-offer, via the "sufficient" allowlist).
    assert match.traffic_light == "yellow"
    assert [c.volume_status for c in match.candidates] == ["adverse_case", "sufficient"]
    assert [c.adverse_case for c in match.candidates] == ["capacity_shortfall", None]
    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor B"]


def test_match_boq_line_downgrades_to_yellow_when_one_source_is_only_reported():
    # P314: "наличие под вопросом" (availability in question) is yellow,
    # same as a stale price or a lone source -- an unverified vendor claim
    # is not "гарантированно" (guaranteed) per §6.4 step 1, even if the
    # volume and freshness checks alone would pass.
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True, executable_status="confirmed"),
        _offer(vendor_id=2, vendor_name="Vendor B", executable_status="reported"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"
    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor A"]


def test_match_boq_line_is_green_when_a_reported_source_is_extra_alongside_two_strong_ones():
    # A weak-availability source never blocks green -- it just doesn't
    # count toward the 2-strong-sources requirement itself.
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True, executable_status="reserved"),
        _offer(vendor_id=2, vendor_name="Vendor B", executable_status="confirmed"),
        _offer(vendor_id=3, vendor_name="Vendor C", executable_status="reported"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "green"


def test_rank_executable_candidates_by_tco_excludes_unknown_availability():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", price=100.0, executable_status="confirmed"),
        _offer(vendor_id=2, vendor_name="Vendor B", price=50.0, executable_status="unknown"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor A"]


def test_negative_reputation_downgraded_status_still_counts_as_strong_when_it_lands_on_confirmed():
    # INV-19: a "reserved" claim from an unreliable vendor is worth about
    # what "confirmed" is from a reliable one -- still strong, not excluded.
    # (The downgrade itself is packages/vendor/availability_model.py's job;
    # here the DTO simply carries the already-downgraded effective value,
    # same as has_negative_reputation is already just a passed-through flag.)
    boq_line = _boq_line()
    offers = [
        _offer(
            vendor_id=1,
            vendor_name="Vendor A",
            has_positive_reputation=True,
            executable_status="reserved",
        ),
        _offer(
            vendor_id=2,
            vendor_name="Vendor B",
            has_negative_reputation=True,
            executable_status="reserved",
            effective_executable_status="confirmed",
        ),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "green"
    assert len(match.ranked_executable) == 2


def test_negative_reputation_downgraded_status_excludes_from_strong_when_it_lands_on_reported():
    # The same downgrade, one tier further: "confirmed" -> "reported" is
    # exactly the tier this task's gate excludes -- INV-19's reputation
    # weighting now visibly changes the traffic light, not just a flag.
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", has_positive_reputation=True, executable_status="confirmed"),
        _offer(
            vendor_id=2,
            vendor_name="Vendor B",
            has_negative_reputation=True,
            executable_status="confirmed",
            effective_executable_status="reported",
        ),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert match.traffic_light == "yellow"
    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor A"]


def test_rank_executable_candidates_by_tco_excludes_a_different_currency():
    boq_line = _boq_line()
    offers = [
        _offer(vendor_id=1, vendor_name="Vendor A", price=100.0, currency="AZN", has_positive_reputation=True),
        _offer(vendor_id=2, vendor_name="Vendor B", price=50.0, currency="USD"),
    ]

    match = match_boq_line(boq_line, offers, as_of=AS_OF)

    assert [c.vendor_name for c, _estimate in match.ranked_executable] == ["Vendor A"]
