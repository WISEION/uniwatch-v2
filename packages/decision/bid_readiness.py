"""Bid readiness computation (task 4.A, TENDER_INTELLIGENCE_SPEC.md §7.1):
the one real, computable half of Bid/No-Bid -- BOQ money coverage against
the spec's own "~85%" lottery threshold, and which BOQ lines depend on
exactly one strong (executable, per task 3.C's Executable Availability)
vendor. Margin, risk concentration, and own-resource-loading are NOT
computed here -- no source document supplies the company's own cost basis
or resource schedule needed for any of them.

`LOTTERY_COVERAGE_THRESHOLD_PCT = 85.0` is copied verbatim from
TENDER_INTELLIGENCE_SPEC.md §7.1 ("покрытие BOQ в деньгах 🟢+🟡 < ~85% ->
участие = лотерея") -- a source-supplied approximate number, not invented
by this task (AGENTS.md hard ban #2 forbids inventing a number nobody
supplied; it does not forbid using one the source document already gives,
tilde and all).

A "critical" line is one where exactly one distinct vendor_id is a strong
source (packages/decision/matching.py::is_strong_source) -- this directly
implements §7.1's Bid/No-Bid criterion "зависимость от единственного
вендора по критической позиции" from data already computed by task 3.D's
matching.py, not a new signal."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from packages.contracts.vendor_api import VendorOfferDTO
from packages.decision.boq_summary import BoqMatchSummary, summarize_boq_matches
from packages.decision.matching import BoqLineMatch, is_strong_source, match_boq_line
from packages.tender.boq_line_model import BoqLine

LOTTERY_COVERAGE_THRESHOLD_PCT = 85.0


@dataclass(frozen=True)
class CriticalLine:
    boqline_source_line_id: int
    vendor_id: int
    vendor_name: str


@dataclass(frozen=True)
class BidReadinessCandidate:
    tender_id: int
    summary: BoqMatchSummary
    is_lottery: bool
    critical_lines: tuple[CriticalLine, ...]
    computed_at: str


def _critical_lines(matches: dict[int, BoqLineMatch]) -> tuple[CriticalLine, ...]:
    critical: list[CriticalLine] = []
    for match in matches.values():
        strong = [c for c in match.candidates if is_strong_source(c)]
        distinct_vendors = {c.vendor_id for c in strong}
        if len(distinct_vendors) == 1:
            sole = strong[0]
            critical.append(
                CriticalLine(
                    boqline_source_line_id=match.boqline_source_line_id,
                    vendor_id=sole.vendor_id,
                    vendor_name=sole.vendor_name,
                )
            )
    return tuple(critical)


def build_bid_readiness_candidate(
    tender_id: int,
    boq_lines: list[BoqLine],
    offers: list[VendorOfferDTO],
    *,
    as_of: datetime,
    computed_at: str,
) -> BidReadinessCandidate:
    matches = {line.source_line_id: match_boq_line(line, offers, as_of=as_of) for line in boq_lines if line.line_type == "normal"}
    summary = summarize_boq_matches(boq_lines, matches)
    coverage_pct = summary.green_pct + summary.yellow_pct
    return BidReadinessCandidate(
        tender_id=tender_id,
        summary=summary,
        is_lottery=coverage_pct < LOTTERY_COVERAGE_THRESHOLD_PCT,
        critical_lines=_critical_lines(matches),
        computed_at=computed_at,
    )
