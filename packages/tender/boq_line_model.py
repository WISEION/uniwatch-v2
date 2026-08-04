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


@dataclass(frozen=True)
class SpecRequirement:
    kind: str  # "concrete_grade" | "rebar_class" | "standard_reference" | "or_equivalent"
    raw_text: str


# Concrete grade: Eurocode-style "B" class (B15..B60) or Soviet/regional
# "marka" style "M" class (M100..M400) -- both are named directly in
# TENDER_INTELLIGENCE_SPEC.md §5.1 ("марка бетона B25/B30"). No other
# concrete-grade notation is implemented until real evidence of one is
# captured.
_CONCRETE_GRADE_RE = re.compile(r"\bB\s?(?:15|20|25|30|35|40|45|50|55|60)\b|\bM\s?(?:100|150|200|250|300|350|400)\b")

# Rebar class: common A-series notations (A-I..A-IV, A400, A500). Best-effort
# pattern set, not an exhaustive locked list -- extend when real evidence
# with a different notation is captured (no source document enumerates the
# full set).
_REBAR_CLASS_RE = re.compile(r"\bA[- ]?(?:I{1,3}|IV|400|500|600)\b")

# Standard reference: AZS / GOST (Latin or Cyrillic) / EN, each followed by
# a number -- exactly the three families TENDER_INTELLIGENCE_SPEC.md §5.1
# names ("стандарт AZS/ГОСТ/EN").
_STANDARD_REFERENCE_RE = re.compile(r"\b(?:AZS|ГОСТ|GOST|EN)\s?\d+(?:[-.]\d+)*\b")

# "Or equivalent": the exact Russian phrase the spec names («или
# эквивалент»), plus its Azerbaijani cognate in the source data's own
# language (used with "və ya", not "ekvivalent" alone -- "ekvivalent" alone
# is too common a loanword to flag by itself) and the English cognate.
_OR_EQUIVALENT_RE = re.compile(
    r"или\s+эквивалент|(?:və\s+ya|ya\s+da)\s+ekvivalent|\bor\s+equivalent\b",
    re.IGNORECASE,
)


def extract_spec_requirements(description: str) -> tuple[SpecRequirement, ...]:
    found: list[SpecRequirement] = []
    for match in _CONCRETE_GRADE_RE.finditer(description):
        found.append(SpecRequirement(kind="concrete_grade", raw_text=match.group(0)))
    for match in _REBAR_CLASS_RE.finditer(description):
        found.append(SpecRequirement(kind="rebar_class", raw_text=match.group(0)))
    for match in _STANDARD_REFERENCE_RE.finditer(description):
        found.append(SpecRequirement(kind="standard_reference", raw_text=match.group(0)))
    for match in _OR_EQUIVALENT_RE.finditer(description):
        found.append(SpecRequirement(kind="or_equivalent", raw_text=match.group(0)))
    return tuple(found)
