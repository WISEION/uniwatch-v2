"""Maps an Execution Ledger deviation to an EXISTING vendor ReputationFact
event_type (Phase 4, task 4.C, feeding SCG's task 3.B reputation layer) --
never a new event_type, never a weighted score (D-VND-REP is still open
and untouched by this module). Only culprit_type == "vendor" observations
ever produce a mapping; anything else returns None, and an unmapped
deviation_category also returns None rather than guessing the closest
existing type."""

from __future__ import annotations

_CATEGORY_TO_EVENT_TYPE = {
    "downtime": "missed_deadline",
    "last_mile": "missed_deadline",
    "rework": "quality_complaint",
}


def map_to_reputation_event_type(deviation_category: str | None, culprit_type: str) -> str | None:
    if culprit_type != "vendor" or deviation_category is None:
        return None
    return _CATEGORY_TO_EVENT_TYPE.get(deviation_category)
