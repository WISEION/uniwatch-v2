"""Pure in-memory diff between two BOQ-line snapshots of the same tender
event (Task 4.B, TENDER_INTELLIGENCE_SPEC.md §7.2, P317). Never writes to
`boq_lines` -- that table has no schema support for a second generation of
the same source_line_id (UNIQUE (source, event_id, source_line_id), no
upsert). Callers pass the CURRENT DB rows as `old` and a fresh, never-stored
live re-fetch as `new`."""

from __future__ import annotations

from .boq_line_model import BoqLine

_COMPARED_FIELDS = ("description", "unit_raw", "qty", "rate", "amount")


def _fingerprint(line: BoqLine) -> tuple:
    return tuple(getattr(line, field) for field in _COMPARED_FIELDS)


def diff_boq_lines(old: list[BoqLine], new: list[BoqLine]) -> tuple[int, ...]:
    old_by_id = {line.source_line_id: line for line in old}
    new_by_id = {line.source_line_id: line for line in new}
    changed = {
        source_line_id
        for source_line_id in set(old_by_id) | set(new_by_id)
        if source_line_id not in old_by_id
        or source_line_id not in new_by_id
        or _fingerprint(old_by_id[source_line_id]) != _fingerprint(new_by_id[source_line_id])
    }
    return tuple(sorted(changed))
