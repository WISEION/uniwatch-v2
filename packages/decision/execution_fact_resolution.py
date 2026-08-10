"""Pure resolution of free-text napkin observations against this codebase's
own already-known BOQ lines and locked-in vendors (Phase 4, task 4.C).
"Planned" data must come from here, never from the photo/voice note itself
-- these functions are how execution_napkin_provider.py bridges OCR'd text
back to a specific boqline_source_line_id / vendor_id.

resolve_boqline_reference uses the same directional, case-insensitive
substring heuristic as matching.py's _material_matches (no better
entity-matching algorithm exists yet, same honest limitation)."""

from __future__ import annotations

from typing import Any

from packages.tender.boq_line_model import BoqLine


def resolve_boqline_reference(boq_lines: list[BoqLine], line_description: str | None) -> BoqLine | None:
    if not line_description:
        return None
    needle = line_description.strip().lower()
    if not needle:
        return None
    for line in boq_lines:
        if needle in line.description.lower():
            return line
    return None


def resolve_vendor_reference(lock_ins: list[dict[str, Any]], culprit_vendor_name: str | None) -> int | None:
    if not culprit_vendor_name:
        return None
    needle = culprit_vendor_name.strip().lower()
    if not needle:
        return None
    for lock_in in lock_ins:
        if lock_in["vendor_name"].strip().lower() == needle:
            return lock_in["vendor_id"]
    return None
