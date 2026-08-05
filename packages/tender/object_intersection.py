"""Composite-trigger intersection primitive (TENDER_INTELLIGENCE_SPEC.md
§5.3, P310). Pure assembly, no DB, no network -- same shape as
signal_model.py/boq_line_model.py.

P310's own definition of a real forecast trigger is exactly this:
"пересечение независимых сигналов по одному объекту, не одиночный сигнал"
(intersection of independent signals on one object, not a single signal).
`is_composite` is that literal boolean fact -- has this object accumulated
signals from 2+ distinct signal_types -- and nothing more.

Deliberately NOT implemented here (both blocked by AGENTS.md hard ban #2 --
never invent a number for a TBD-nn placeholder):
- Section 5.3's weak/medium/strong confidence tiers. The spec's own text is
  explicit that the illustrative ~30%/60%/85% figures are "a shape of the
  model, not calibrated thresholds" -- the real numbers are TBD-TIS-02,
  pending the P310 backtest (>=30 already-published tenders). The tier
  compositions the spec names (e.g. weak = "program line + strategy
  mention") also reference signal categories (decrees, budgets) this
  project has no source for yet, so there is no honest mapping from
  signal_type count to a named tier today.
- TTL-based decay / "frozen" object state. `ttl_class` on a Signal is a
  label only (see signal_model.py) -- actual expiry durations are
  TBD-TIS-01. Without a duration, "is this chain broken" can't be computed
  without inventing one.

Both are recorded as open in docs/decisions/OPEN-QUESTIONS.md rather than
faked with placeholder numbers."""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ObjectIntersection:
    object_region: str
    signal_types: frozenset[str]
    is_composite: bool


def detect_intersection(object_region: str, signal_rows: Sequence[dict[str, Any]]) -> ObjectIntersection:
    signal_types = frozenset(row["signal_type"] for row in signal_rows)
    return ObjectIntersection(
        object_region=object_region,
        signal_types=signal_types,
        is_composite=len(signal_types) >= 2,
    )
