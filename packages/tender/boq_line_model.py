"""Atomic BOQ line model (FR-TND-*, TENDER_INTELLIGENCE_SPEC.md §5.1, P308).

Pure functions only -- no DB import in this module. `build_boq_lines`
assembles one `BoqLine` per source item; persistence is
`boq_lines_store.store_boq_lines`, kept separate so this module's logic is
testable without Postgres.

Unit canonicalization only maps units actually observed in real captured
fixtures (see MANIFEST.md) plus a handful of unambiguous SI/construction
units (m2, m3, kg, t, l) certain to appear in any BOQ. An unrecognized unit
is never guessed at -- it is flagged `unmapped` and the raw string is kept,
so a downstream matching/calculation step can see exactly which lines have
an unresolved unit rather than silently trusting a wrong canonicalization
(INV-11)."""

from __future__ import annotations

import re
from dataclasses import dataclass

_UNIT_CANONICAL_MAP: dict[str, str] = {
    "ədəd": "pcs",  # Azerbaijani "piece" -- observed on all 3 real captured pages
    "dəst": "set",  # Azerbaijani "set" -- observed on real captured page 3
    "m": "m",
    "m2": "m2",
    "m²": "m2",
    "m3": "m3",
    "m³": "m3",
    "kg": "kg",
    "t": "t",
    "l": "l",
}


@dataclass(frozen=True)
class CanonicalUnit:
    raw: str
    canonical: str | None
    status: str  # "mapped" | "unmapped"


def canonicalize_unit(raw_unit: str) -> CanonicalUnit:
    canonical = _UNIT_CANONICAL_MAP.get(raw_unit)
    status = "mapped" if canonical is not None else "unmapped"
    return CanonicalUnit(raw=raw_unit, canonical=canonical, status=status)


# Keyword sets are deliberately English-only, matching the exact terms
# TENDER_INTELLIGENCE_SPEC.md §5.1 names ("preliminaries", "provisional
# sums", "prime cost"). No Azerbaijani/Russian equivalents are guessed at
# here -- none are supplied by any source document, and inventing a
# translation would be exactly the kind of unsourced fact AGENTS.md hard
# ban #2 forbids. See docs/decisions/OPEN-QUESTIONS.md (2026-08-05, task
# 2.A entry) for the resulting open question to the owner.
_PRELIMINARIES_RE = re.compile(r"\bpreliminar(?:y|ies)\b", re.IGNORECASE)
_PROVISIONAL_SUM_RE = re.compile(r"\bprovisional\s+sums?\b", re.IGNORECASE)
_PRIME_COST_RE = re.compile(r"\bprime\s+cost\b|\bPC\s+sum\b", re.IGNORECASE)


def classify_line_type(name: str, description: str) -> str:
    text = f"{name} {description}"
    if _PRELIMINARIES_RE.search(text):
        return "preliminaries"
    if _PROVISIONAL_SUM_RE.search(text):
        return "provisional_sum"
    if _PRIME_COST_RE.search(text):
        return "prime_cost"
    return "normal"
