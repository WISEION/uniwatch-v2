"""BOQ-wide traffic-light summary by money (task 3.D, P315:
"BOQ раскрашен ... выдаётся сводка «X% зелёного / Y% жёлтого / Z%
красного по деньгам»"). A line with no `amount` (source never supplied
one) is counted in `unpriced_amount`, never silently dropped from the
picture or folded into 0% (AGENTS.md hard ban #3)."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from packages.decision.matching import BoqLineMatch
from packages.tender.boq_line_model import BoqLine


@dataclass(frozen=True)
class BoqMatchSummary:
    green_amount: Decimal
    yellow_amount: Decimal
    red_amount: Decimal
    unpriced_amount: Decimal
    total_priced_amount: Decimal
    green_pct: float
    yellow_pct: float
    red_pct: float


def summarize_boq_matches(boq_lines: list[BoqLine], matches: dict[int, BoqLineMatch]) -> BoqMatchSummary:
    amounts_by_light: dict[str, Decimal] = {"green": Decimal("0"), "yellow": Decimal("0"), "red": Decimal("0")}
    unpriced_amount = Decimal("0")

    for boq_line in boq_lines:
        match = matches[boq_line.source_line_id]
        if boq_line.amount is None:
            unpriced_amount += Decimal("0")
            continue
        amounts_by_light[match.traffic_light] += boq_line.amount

    total_priced_amount = amounts_by_light["green"] + amounts_by_light["yellow"] + amounts_by_light["red"]

    def pct(amount: Decimal) -> float:
        if total_priced_amount == 0:
            return 0.0
        return float(amount / total_priced_amount * 100)

    return BoqMatchSummary(
        green_amount=amounts_by_light["green"],
        yellow_amount=amounts_by_light["yellow"],
        red_amount=amounts_by_light["red"],
        unpriced_amount=unpriced_amount,
        total_priced_amount=total_priced_amount,
        green_pct=pct(amounts_by_light["green"]),
        yellow_pct=pct(amounts_by_light["yellow"]),
        red_pct=pct(amounts_by_light["red"]),
    )
