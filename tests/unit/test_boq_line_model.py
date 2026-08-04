"""FR-TND-*: unit canonicalization never guesses -- an unmapped unit keeps
its raw string and is flagged 'unmapped', not silently coerced to a wrong
canonical unit (INV-11 no silent fallback)."""

from __future__ import annotations

from packages.tender.boq_line_model import CanonicalUnit, canonicalize_unit


def test_canonicalizes_real_captured_units():
    # These three are the only unitOfMeasure values observed across all
    # three real captured pages of event 355920 (see MANIFEST.md).
    assert canonicalize_unit("ədəd") == CanonicalUnit(raw="ədəd", canonical="pcs", status="mapped")
    assert canonicalize_unit("m") == CanonicalUnit(raw="m", canonical="m", status="mapped")
    assert canonicalize_unit("dəst") == CanonicalUnit(raw="dəst", canonical="set", status="mapped")


def test_canonicalizes_other_unambiguous_construction_units():
    assert canonicalize_unit("kg") == CanonicalUnit(raw="kg", canonical="kg", status="mapped")
    assert canonicalize_unit("m2") == CanonicalUnit(raw="m2", canonical="m2", status="mapped")
    assert canonicalize_unit("m3") == CanonicalUnit(raw="m3", canonical="m3", status="mapped")


def test_unmapped_unit_keeps_raw_string_and_is_flagged_not_guessed():
    result = canonicalize_unit("qutu")  # "box" -- not in the canonical map
    assert result.canonical is None
    assert result.status == "unmapped"
    assert result.raw == "qutu"


def test_canonicalize_unit_helper_returns_dataclass():
    result = canonicalize_unit("m")
    assert isinstance(result, CanonicalUnit)
