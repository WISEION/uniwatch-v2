"""Unit tests for CsvProvider (TENDER_INTELLIGENCE_SPEC.md §6.1, FR-VND-04's
second required Phase 3 provider). The CSV content here is a parser-format
fixture -- it proves the parsing logic, not a claim about any real
vendor's actual prices (no real vendor CSV exists in this session)."""

from __future__ import annotations

import pytest

from packages.vendor.csv_provider import CsvParseError, CsvProvider

AS_OF = "2026-08-06T00:00:00+00:00"

SAMPLE_CSV = (
    "vendor_name,material,price,currency,vat_rate,uom,uom_canonical_qty,"
    "moq,capacity,inventory,valid_from,valid_until\n"
    "CSV Rebar Co,rebar-16mm,870.50,AZN,18.0,ton,1.0,5,150,90,"
    "2026-08-01T00:00:00+00:00,2026-09-15T00:00:00+00:00\n"
    "CSV Cement Co,cement-42.5,180.00,AZN,18.0,ton,1.0,2,400,250,"
    "2026-08-01T00:00:00+00:00,2026-09-15T00:00:00+00:00\n"
)


def test_parses_every_row_into_a_vendor_and_offer():
    vendors, offers = CsvProvider(csv_content=SAMPLE_CSV).generate(as_of=AS_OF)
    assert len(vendors) == 2
    assert len(offers) == 2
    assert {v.name for v in vendors} == {"CSV Rebar Co", "CSV Cement Co"}
    rebar = next(o for o in offers if o.material == "rebar-16mm")
    assert rebar.price == 870.50
    assert rebar.currency == "AZN"
    assert rebar.vat_rate == 18.0
    assert rebar.uom == "ton"
    assert rebar.moq == 5.0
    assert rebar.capacity == 150.0
    assert rebar.inventory == 90.0
    assert rebar.vendor_name == "CSV Rebar Co"


def test_every_parsed_record_is_sandbox_realm_and_synthetic_watermarked():
    # ADR-0004: the real vendor onboarding gate hasn't opened, so every
    # provider's output stays sandbox/SYNTHETIC regardless of input shape.
    vendors, offers = CsvProvider(csv_content=SAMPLE_CSV).generate(as_of=AS_OF)
    assert all(v.data_realm == "vendor-sandbox" and v.watermark == "SYNTHETIC" for v in vendors)
    assert all(o.data_realm == "vendor-sandbox" and o.watermark == "SYNTHETIC" for o in offers)


def test_evidence_source_and_observed_at_are_set_from_as_of():
    _vendors, offers = CsvProvider(csv_content=SAMPLE_CSV).generate(as_of=AS_OF)
    assert all(o.evidence_source == "csv-upload" for o in offers)
    assert all(o.observed_at == AS_OF for o in offers)
    assert all(o.adverse_case is None for o in offers)


def test_empty_csv_content_produces_no_records():
    header_only = (
        "vendor_name,material,price,currency,vat_rate,uom,uom_canonical_qty,moq,capacity,inventory,valid_from,valid_until\n"
    )
    vendors, offers = CsvProvider(csv_content=header_only).generate(as_of=AS_OF)
    assert vendors == []
    assert offers == []


def test_missing_required_column_raises_a_typed_error():
    malformed_csv = "vendor_name,material,price\nX,Y,1.0\n"
    with pytest.raises(CsvParseError):
        CsvProvider(csv_content=malformed_csv).generate(as_of=AS_OF)
