"""BOQ <-> SCG matching, inverted logic (task 3.D, TENDER_INTELLIGENCE_SPEC.md
§6.4, INV-19, P315): executability first, then price. Pure functions, no DB
-- packages/decision is the sanctioned home for logic needing both
packages/tender's BoqLine (in-process, tender/decision not split by
ADR-0006) and Vendor offer data (only via packages/contracts, never a
direct packages/vendor import -- ADR-0006 names "a future packages/decision
that needs both" as the intended caller of that contract).

Material matching is a case-insensitive substring heuristic (offer
material found inside the BOQ line description) -- no source document
supplies a real entity-matching algorithm for this yet, and this is the
same deterministic-heuristic discipline as boq_line_model.py's spec-keyword
regexes. The check is directional (offer.material must appear inside
boq_line.description, not the reverse) since the BOQ description is
normally the longer, more descriptive text.

Volume sufficiency only compares offer.inventory (on-hand stock, not
offer.capacity's production *rate*, which cannot be compared to a flat BOQ
quantity without a delivery window BoqLine does not carry) against the BOQ
line's qty, and only when both units canonicalize to the same value -- an
unmapped/mismatched unit is a distinct status, never silently treated as
either a match or a non-match (AGENTS.md hard ban #3). An offer carrying a
non-null `adverse_case` (packages/vendor/synthetic_provider.py's seven
FR-VND-03 cases -- moq_conflict, mixed_uom, currency_vat_mismatch,
capacity_shortfall, expiring_evidence, partial_fulfillment; stale_offer is
already caught by the freshness check below) is excluded from "sufficient"
via its own status rather than silently scored as a clean match -- the
generator's own docstring names this exclusion as this task's job. It
still counts as an existing source (not "nobody has it") since the data
isn't proven absent, just flagged as needing an explicit human decision
per FR-VND-03.

`price_with_vat` treats `vat_rate` as a PERCENT (18.0 means 18%), matching
the only real producer of this field, packages/vendor/synthetic_provider.py
-- not a fraction (0.18). Getting this backwards inflates every price by
~19x, which is exactly what this module did before this fix; there is no
test that would catch that without exercising a real (seed, as_of)
generator run, which is why tests/unit/test_matching_against_synthetic_provider.py
exists.

Cross-currency candidates are never merged into one price ranking (no FX
rate is invented, per hard ban #2/D-TAX): `rank_executable_candidates_by_tco`
only ranks the executable subset that shares the plurality currency among
themselves (a tie on count is broken deterministically by taking the
alphabetically first currency code); candidates in a different currency stay visible on
`BoqLineMatch.candidates` (with their own `currency` field) but are
excluded from `ranked_executable`, never numerically compared across
currencies.

TCO here is base_price_with_vat only -- logistics/financing/insurance/
risk_reserve(reputation) have no source-supplied formula (D-VND-REP covers
the reputation term; see docs/decisions/OPEN-QUESTIONS.md for the rest),
so `TcoEstimate.status` is always "partial_price_only", never a silent 0
for the missing terms."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal

from packages.contracts.vendor_api import VendorOfferDTO
from packages.tender.boq_line_model import BoqLine, canonicalize_unit


@dataclass(frozen=True)
class MatchCandidate:
    boqline_source_line_id: int
    offer_id: int
    vendor_id: int
    vendor_name: str
    material: str
    data_realm: str
    watermark: str
    currency: str
    freshness: str  # "fresh" | "stale"
    volume_status: str  # "sufficient" | "insufficient" | "unit_mismatch" | "unit_unmapped" | "adverse_case"
    has_positive_reputation: bool
    has_negative_reputation: bool
    price_with_vat: Decimal


@dataclass(frozen=True)
class TcoEstimate:
    base_price_with_vat: Decimal
    status: str  # always "partial_price_only" in this slice


@dataclass(frozen=True)
class BoqLineMatch:
    boqline_source_line_id: int
    traffic_light: str  # "green" | "yellow" | "red"
    candidates: tuple[MatchCandidate, ...]
    ranked_executable: tuple[tuple[MatchCandidate, TcoEstimate], ...]


def _material_matches(boq_line: BoqLine, offer_material: str) -> bool:
    material = offer_material.strip().lower()
    if not material:
        return False
    return material in boq_line.description.lower()


def _freshness(offer: VendorOfferDTO, as_of: datetime) -> str:
    return "fresh" if as_of <= offer.valid_until else "stale"


def _volume_status(boq_line: BoqLine, offer: VendorOfferDTO) -> str:
    if offer.adverse_case is not None:
        return "adverse_case"
    if boq_line.unit_status != "mapped":
        return "unit_unmapped"
    offer_unit = canonicalize_unit(offer.uom)
    if offer_unit.status != "mapped":
        return "unit_unmapped"
    if offer_unit.canonical != boq_line.unit_canonical:
        return "unit_mismatch"
    if Decimal(str(offer.inventory)) >= boq_line.qty:
        return "sufficient"
    return "insufficient"


def _price_with_vat(offer: VendorOfferDTO) -> Decimal:
    return Decimal(str(offer.price)) * (Decimal("1") + Decimal(str(offer.vat_rate)) / Decimal("100"))


def classify_candidate(boq_line: BoqLine, offer: VendorOfferDTO, *, as_of: datetime) -> MatchCandidate:
    return MatchCandidate(
        boqline_source_line_id=boq_line.source_line_id,
        offer_id=offer.id,
        vendor_id=offer.vendor_id,
        vendor_name=offer.vendor_name,
        material=offer.material,
        data_realm=offer.data_realm,
        watermark=offer.watermark,
        currency=offer.currency,
        freshness=_freshness(offer, as_of),
        volume_status=_volume_status(boq_line, offer),
        has_positive_reputation=offer.has_positive_reputation,
        has_negative_reputation=offer.has_negative_reputation,
        price_with_vat=_price_with_vat(offer),
    )


def _traffic_light(candidates: tuple[MatchCandidate, ...]) -> str:
    sources = tuple(c for c in candidates if c.volume_status != "insufficient")
    if not sources:
        return "red"
    confirmed_fresh_by_vendor = {c.vendor_id: c for c in sources if c.volume_status == "sufficient" and c.freshness == "fresh"}
    if len(confirmed_fresh_by_vendor) >= 2 and any(c.has_positive_reputation for c in confirmed_fresh_by_vendor.values()):
        return "green"
    return "yellow"


def rank_executable_candidates_by_tco(
    candidates: tuple[MatchCandidate, ...],
) -> tuple[tuple[MatchCandidate, TcoEstimate], ...]:
    executable = [c for c in candidates if c.volume_status == "sufficient" and c.freshness == "fresh"]
    if not executable:
        return ()
    currency_counts: dict[str, int] = {}
    for c in executable:
        currency_counts[c.currency] = currency_counts.get(c.currency, 0) + 1
    reference_currency = min(currency_counts, key=lambda cur: (-currency_counts[cur], cur))
    comparable = [c for c in executable if c.currency == reference_currency]
    ranked = sorted(comparable, key=lambda c: c.price_with_vat)
    return tuple((c, TcoEstimate(base_price_with_vat=c.price_with_vat, status="partial_price_only")) for c in ranked)


def match_boq_line(boq_line: BoqLine, offers: list[VendorOfferDTO], *, as_of: datetime) -> BoqLineMatch:
    candidates = tuple(
        classify_candidate(boq_line, offer, as_of=as_of) for offer in offers if _material_matches(boq_line, offer.material)
    )
    return BoqLineMatch(
        boqline_source_line_id=boq_line.source_line_id,
        traffic_light=_traffic_light(candidates),
        candidates=candidates,
        ranked_executable=rank_executable_candidates_by_tco(candidates),
    )
