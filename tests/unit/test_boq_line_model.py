"""FR-TND-*: unit canonicalization never guesses -- an unmapped unit keeps
its raw string and is flagged 'unmapped', not silently coerced to a wrong
canonical unit (INV-11 no silent fallback)."""

from __future__ import annotations

from packages.tender.boq_line_model import (
    CanonicalUnit,
    SpecRequirement,
    canonicalize_unit,
    classify_line_type,
    extract_spec_requirements,
)


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


def test_classifies_preliminaries_by_keyword():
    assert classify_line_type("Preliminaries", "Site preliminaries and general conditions") == "preliminaries"


def test_classifies_provisional_sum_by_keyword():
    assert classify_line_type("General", "Provisional sum for unforeseen ground conditions") == "provisional_sum"
    assert classify_line_type("General", "Provisional sums for utility connections") == "provisional_sum"


def test_classifies_prime_cost_by_keyword():
    assert classify_line_type("General", "Prime cost sum for lift installation") == "prime_cost"
    assert classify_line_type("General", "PC sum: sanitary fittings") == "prime_cost"


def test_defaults_to_normal_for_an_ordinary_line():
    # Real line from event_355920_bomlines_page1.raw.json -- must not be
    # misclassified just because it mentions a device/cabinet.
    assert (
        classify_line_type(
            "Əsas korpus - Elektrik təchizatı və güc avadanlıqı (Blok A1-A2)",  # noqa: RUF001
            "Metal şkaf 800x600x250mm",
        )
        == "normal"
    )


def test_classification_is_case_insensitive():
    assert classify_line_type("x", "PRELIMINARIES") == "preliminaries"


def test_extracts_concrete_grade():
    reqs = extract_spec_requirements("Beton B25 tökülməsi, qalınlığı 200mm")  # noqa: RUF001
    assert SpecRequirement(kind="concrete_grade", raw_text="B25") in reqs


def test_extracts_marka_style_concrete_grade():
    reqs = extract_spec_requirements("Beton M300 markalı")  # noqa: RUF001
    assert SpecRequirement(kind="concrete_grade", raw_text="M300") in reqs


def test_extracts_standard_reference_azs():
    reqs = extract_spec_requirements("AZS 1234-2020 standartına uyğun")  # noqa: RUF001
    assert SpecRequirement(kind="standard_reference", raw_text="AZS 1234-2020") in reqs


def test_extracts_standard_reference_gost():
    reqs = extract_spec_requirements("ГОСТ 5781 armaturu")
    assert SpecRequirement(kind="standard_reference", raw_text="ГОСТ 5781") in reqs


def test_extracts_standard_reference_en():
    reqs = extract_spec_requirements("cable per EN 60228")
    assert SpecRequirement(kind="standard_reference", raw_text="EN 60228") in reqs


def test_extracts_or_equivalent_russian_phrase_from_spec():
    # Literal phrase TENDER_INTELLIGENCE_SPEC.md §5.1 names.
    reqs = extract_spec_requirements("кабель ВВГ или эквивалент")
    assert any(r.kind == "or_equivalent" for r in reqs)


def test_extracts_or_equivalent_azerbaijani_phrase():
    reqs = extract_spec_requirements("Şkaf və ya ekvivalent")
    assert any(r.kind == "or_equivalent" for r in reqs)


def test_extracts_or_equivalent_english_phrase():
    reqs = extract_spec_requirements("steel cabinet or equivalent")
    assert any(r.kind == "or_equivalent" for r in reqs)


def test_no_false_positive_on_a_plain_real_description():
    # Real description from event_355920_bomlines_page1.raw.json -- no
    # hidden spec requirement of any kind actually present in it.
    reqs = extract_spec_requirements("Cihaz və ya aparatların quraşdırılması")  # noqa: RUF001
    # "və ya" appears here but is NOT followed by "ekvivalent" -- must not
    # be flagged as or_equivalent just because "və ya" is present.
    assert reqs == ()


def test_extracts_multiple_requirements_from_one_description():
    reqs = extract_spec_requirements("Beton B30, AZS 5678 standartına uyğun, və ya ekvivalent")  # noqa: RUF001
    kinds = {r.kind for r in reqs}
    assert kinds == {"concrete_grade", "standard_reference", "or_equivalent"}
