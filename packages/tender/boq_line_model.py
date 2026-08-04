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
