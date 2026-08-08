"""Unit tests for packages/decision/bid_readiness.py (task 4.A,
TENDER_INTELLIGENCE_SPEC.md §7.1's Bid/No-Bid coverage rule: "покрытие BOQ
в деньгах 🟢+🟡 < ~85% -> участие = лотерея"). Pure functions, no DB --
reuses packages/decision/matching.py's own real match_boq_line, not a
hand-rolled reimplementation."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from packages.contracts.vendor_api import VendorOfferDTO
from packages.decision.bid_readiness import LOTTERY_COVERAGE_THRESHOLD_PCT, build_bid_readiness_candidate
from packages.tender.boq_line_model import BoqLine

AS_OF = datetime.fromisoformat("2026-08-08T00:00:00+00:00")


def _boq_line(source_line_id: int, description: str, amount: str, line_type: str = "normal") -> BoqLine:
    return BoqLine(
        source_line_id=source_line_id,
        page_number=1,
        section=None,
        category_code=None,
        description=description,
        unit_raw="t",
        unit_canonical="t",
        unit_status="mapped",
        qty=Decimal("10"),
        line_type=line_type,
        spec_requirements=(),
        rate=Decimal("100"),
        amount=Decimal(amount),
    )


def _offer(
    vendor_id: int,
    vendor_name: str,
    material: str,
    *,
    has_positive_reputation: bool = False,
    executable_status: str = "reserved",
) -> VendorOfferDTO:
    return VendorOfferDTO(
        id=vendor_id,
        vendor_id=vendor_id,
        vendor_name=vendor_name,
        data_realm="vendor-sandbox",
        watermark="SYNTHETIC",
        material=material,
        price=100.0,
        currency="AZN",
        vat_rate=18.0,
        uom="t",
        uom_canonical_qty=1.0,
        moq=1.0,
        capacity=100.0,
        inventory=40.0,
        valid_from="2026-08-01T00:00:00+00:00",
        valid_until="2026-09-01T00:00:00+00:00",
        evidence_source="test",
        observed_at="2026-08-01T00:00:00+00:00",
        adverse_case=None,
        executable_status=executable_status,
        effective_executable_status=executable_status,
        has_positive_reputation=has_positive_reputation,
        has_negative_reputation=False,
    )


def test_full_coverage_with_two_strong_vendors_is_not_a_lottery():
    boq_lines = [_boq_line(1, "rebar-12mm", "1000")]
    offers = [
        _offer(1, "Vendor A", "rebar-12mm", has_positive_reputation=True),
        _offer(2, "Vendor B", "rebar-12mm"),
    ]

    candidate = build_bid_readiness_candidate(42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00")

    assert candidate.tender_id == 42
    assert candidate.summary.green_pct == 100.0
    assert candidate.is_lottery is False
    assert candidate.critical_lines == ()


def test_zero_coverage_is_a_lottery():
    boq_lines = [_boq_line(1, "excavation works", "1000")]
    offers = [_offer(1, "Vendor A", "rebar-12mm")]

    candidate = build_bid_readiness_candidate(42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00")

    assert candidate.summary.red_pct == 100.0
    assert candidate.is_lottery is True


def test_lottery_threshold_matches_the_spec_constant():
    assert LOTTERY_COVERAGE_THRESHOLD_PCT == 85.0


def test_single_vendor_line_is_flagged_critical():
    boq_lines = [_boq_line(1, "rebar-12mm", "1000")]
    offers = [_offer(1, "Vendor A", "rebar-12mm")]

    candidate = build_bid_readiness_candidate(42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00")

    assert len(candidate.critical_lines) == 1
    assert candidate.critical_lines[0].boqline_source_line_id == 1
    assert candidate.critical_lines[0].vendor_id == 1


def test_two_strong_vendor_line_is_not_flagged_critical():
    boq_lines = [_boq_line(1, "rebar-12mm", "1000")]
    offers = [
        _offer(1, "Vendor A", "rebar-12mm", has_positive_reputation=True),
        _offer(2, "Vendor B", "rebar-12mm"),
    ]

    candidate = build_bid_readiness_candidate(42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00")

    assert candidate.critical_lines == ()


def test_non_matchable_line_type_is_excluded_and_not_critical():
    boq_lines = [_boq_line(1, "preliminaries and general conditions", "500", line_type="preliminaries")]
    offers = [_offer(1, "Vendor A", "rebar-12mm")]

    candidate = build_bid_readiness_candidate(42, boq_lines, offers, as_of=AS_OF, computed_at="2026-08-08T00:00:00+00:00")

    assert candidate.summary.non_matchable_line_count == 1
    assert candidate.critical_lines == ()
