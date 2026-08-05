"""Forecast-card evidence assembly (TENDER_INTELLIGENCE_SPEC.md §5.4,
P311). Pure assembly, no DB, no network -- same shape as
object_intersection.py/signal_model.py.

P311: "карточка собирается только при пороге, содержит проверяемую
цепочку улик" (a card is assembled only at threshold, and contains a
verifiable evidence chain). The real threshold (>=50%, three calibrated
probabilities) is TBD-TIS-02 -- no calibrated model exists yet. This
module substitutes the real, non-fabricated `is_composite` boolean
(object_intersection.py, task 2.C) as an honest stand-in for that
still-missing threshold: `build_forecast_card` returns None exactly when
`detect_intersection(...).is_composite` is False, refusing to assemble a
card at all below that bar -- the same "don't build it below threshold"
intent as P311, just gated on a real fact instead of an uncalibrated
percentage. Recorded as a deliberate deviation in
docs/decisions/OPEN-QUESTIONS.md, not silently presented as satisfying
the spec's literal wording.

Deliberately NOT built here (recorded as open, not invented):
- The spec's three probabilities and publication window -- both need the
  same TBD-TIS-02 calibration the tier work in object_intersection.py
  already deferred.
- Next Best Action -- no source document defines what this text should
  say; inventing one would be exactly the kind of fabrication this
  project's hard bans forbid.
- Delivery (weekly digest / urgent alert) -- a separate future task, not
  part of assembling the card itself.

"оценка бюджета" (budget estimate) is real, not calibrated: it is
whatever monetary field a signal's own source document already carries,
surfaced as-is. Today only `donor_pipeline_project` signals
(signal_model.py's build_donor_pipeline_signal) carry one
(`total_amount_usd_text`, plus `url`) -- design_tender/procurement_plan
signals carry no monetary field at all, so budget_estimate is honestly
None for an object with only those types accumulated.

"цепочка улик... со ссылками" (evidence chain with links): only
donor_pipeline_project signals carry a real clickable `url`.
design_tender/procurement_plan signals carry none (eTender's events-list/
app-list resources don't expose one) -- inventing a guessed URL pattern
would fabricate a fact never actually captured. Every evidence entry
does carry raw_snapshot_id, a real, always-present, verifiable pointer to
its own raw evidence bytes -- used as the honest "link" surrogate where no
real URL exists."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any

from .object_intersection import detect_intersection


@dataclass(frozen=True)
class ForecastCard:
    object_region: str
    is_composite: bool
    signal_types: frozenset[str]
    budget_estimate: dict[str, Any] | None
    evidence_chain: tuple[dict[str, Any], ...]


def build_forecast_card(object_region: str, signal_rows: Sequence[dict[str, Any]]) -> ForecastCard | None:
    intersection = detect_intersection(object_region, signal_rows)
    if not intersection.is_composite:
        return None

    budget_estimate: dict[str, Any] | None = None
    for row in signal_rows:
        if row["signal_type"] == "donor_pipeline_project":
            budget_estimate = {"source": "donor_pipeline_project", **row["value"]}
            break

    evidence_chain = tuple(
        {
            "signal_type": row["signal_type"],
            "source": row["source"],
            "observed_at": row["observed_at"],
            "raw_snapshot_id": row["raw_snapshot_id"],
            "value": row["value"],
        }
        for row in signal_rows
    )

    return ForecastCard(
        object_region=object_region,
        is_composite=True,
        signal_types=intersection.signal_types,
        budget_estimate=budget_estimate,
        evidence_chain=evidence_chain,
    )
