"""Runs the real packages/vendor/synthetic_provider.py generator through
packages/decision/matching.py and boq_summary.py -- every other test in
this branch used hand-written VendorOfferDTO fixtures, which is exactly
what let the VAT-convention bug (vat_rate as percent vs fraction), the
cross-currency ranking bug, the dropped adverse_case field, and the
uom="ton" canonicalization gap all ship past six task-level reviews: none
of them exercised two components against the repo's one real data
producer at the same time. This test is that missing seam."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from packages.contracts.vendor_api import VendorOfferDTO
from packages.decision.boq_summary import summarize_boq_matches
from packages.decision.matching import match_boq_line
from packages.tender.boq_line_model import BoqLine
from packages.vendor.synthetic_provider import SyntheticProvider

AS_OF = "2026-08-06T00:00:00+00:00"


def _offer_to_dto(offer, *, offer_id: int, vendor_id: int) -> VendorOfferDTO:
    return VendorOfferDTO(
        id=offer_id,
        vendor_id=vendor_id,
        vendor_name=offer.vendor_name,
        data_realm=offer.data_realm,
        watermark=offer.watermark,
        material=offer.material,
        price=offer.price,
        currency=offer.currency,
        vat_rate=offer.vat_rate,
        uom=offer.uom,
        uom_canonical_qty=offer.uom_canonical_qty,
        moq=offer.moq,
        capacity=offer.capacity,
        inventory=offer.inventory,
        valid_from=offer.valid_from,
        valid_until=offer.valid_until,
        evidence_source=offer.evidence_source,
        observed_at=offer.observed_at,
        adverse_case=offer.adverse_case,
        has_positive_reputation=False,
        has_negative_reputation=False,
    )


def _rebar_boq_line() -> BoqLine:
    return BoqLine(
        source_line_id=1,
        page_number=1,
        section=None,
        category_code=None,
        description="Supply of rebar-12mm reinforcement steel",
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type="normal",
        spec_requirements=(),
        rate=Decimal("850"),
        amount=Decimal("8500"),
    )


def test_the_one_clean_generator_offer_reaches_sufficient_with_a_sane_price():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    dtos = [_offer_to_dto(o, offer_id=i, vendor_id=i) for i, o in enumerate(offers)]
    boq_line = _rebar_boq_line()

    match = match_boq_line(boq_line, dtos, as_of=datetime.fromisoformat(AS_OF))

    clean_candidates = [c for c in match.candidates if c.volume_status == "sufficient"]
    assert len(clean_candidates) == 1
    clean = clean_candidates[0]
    # price is in the 800-900 AZN range at 18% VAT -- a correct fraction-based
    # computation lands well under 1100; the pre-fix bug (treating 18.0 as a
    # fraction) would have produced a price over 15000.
    assert Decimal("900") < clean.price_with_vat < Decimal("1100")


def test_all_seven_adverse_case_offers_are_excluded_from_ranked_executable():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    dtos = [_offer_to_dto(o, offer_id=i, vendor_id=i) for i, o in enumerate(offers)]
    boq_line = _rebar_boq_line()

    match = match_boq_line(boq_line, dtos, as_of=datetime.fromisoformat(AS_OF))

    # Only the one clean "rebar-12mm" offer matches this BOQ line's
    # description at all (the other 7 offers are different materials that
    # don't substring-match "rebar-12mm reinforcement steel" -- except the
    # mixed_uom adverse case, which IS the same material "rebar-12mm").
    adverse_candidates = [c for c in match.candidates if c.material == "rebar-12mm" and c.volume_status == "adverse_case"]
    assert len(adverse_candidates) == 1
    assert match.ranked_executable == () or all(c.volume_status == "sufficient" for c, _estimate in match.ranked_executable)


def test_summarize_boq_matches_runs_clean_against_real_generator_output():
    _vendors, offers = SyntheticProvider(seed=1).generate(as_of=AS_OF)
    dtos = [_offer_to_dto(o, offer_id=i, vendor_id=i) for i, o in enumerate(offers)]
    boq_line = _rebar_boq_line()

    match = match_boq_line(boq_line, dtos, as_of=datetime.fromisoformat(AS_OF))
    summary = summarize_boq_matches([boq_line], {boq_line.source_line_id: match})

    assert summary.green_pct + summary.yellow_pct + summary.red_pct == 100.0
