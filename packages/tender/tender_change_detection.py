"""Pure diff logic for detecting a tracked tender's event_details changing
between two ingested tender_versions (Task 4.B, TENDER_INTELLIGENCE_SPEC.md
§7.2, P317). No DB access here -- packages/tender/post_submission_tracking_job.py
loads the two normalized_fields dicts and calls into this module."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEADLINE_FIELDS = frozenset({"end_date", "envelope_date", "start_date"})

# "id" is the numeric event id bridge added for Task 4.A's C1 fix -- it is
# the tender's own stable identity, not a fact about the tender that could
# legitimately "change" between two versions of the SAME tender, so a diff
# must never report it (it would falsely look like a change on the rare
# occasion a caller compares fields across two different tenders by mistake).
_IGNORED_FIELDS = frozenset({"id"})


@dataclass(frozen=True)
class TenderFieldChange:
    field: str
    old_value: Any
    new_value: Any


def diff_normalized_fields(old: dict[str, Any], new: dict[str, Any]) -> tuple[TenderFieldChange, ...]:
    keys = (set(old) | set(new)) - _IGNORED_FIELDS
    changes = [
        TenderFieldChange(field=key, old_value=old.get(key), new_value=new.get(key))
        for key in sorted(keys)
        if old.get(key) != new.get(key)
    ]
    return tuple(changes)


def classify_change_type(changes: tuple[TenderFieldChange, ...]) -> str:
    if any(change.field in DEADLINE_FIELDS for change in changes):
        return "deadline_shift"
    return "document_changed"
