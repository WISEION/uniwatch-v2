"""Unit tests for the official-source registry domain model (Phase 5, task
5.A, FR-ALG-23). No real law/FX/VAT/price-index value appears here -- every
example below is explicitly synthetic test fixture data."""

from __future__ import annotations

import pytest

from packages.algorithm.official_source_registry_model import OfficialSource


def _source(**overrides) -> OfficialSource:
    base = {
        "source_type": "fx_rate",
        "name": "USD/AZN",
        "citation": "test-fixture-only, not a real published rate",
        "value": "1.0000",
        "effective_from": "2026-01-01T00:00:00+00:00",
        "entered_by": "algo_owner",
        "entered_at": "2026-08-12T00:00:00+00:00",
    }
    base.update(overrides)
    return OfficialSource(**base)


def test_accepts_all_four_source_types():
    for source_type in ("law", "fx_rate", "vat_rate", "price_index"):
        source = _source(source_type=source_type)
        assert source.source_type == source_type


def test_rejects_unknown_source_type():
    with pytest.raises(ValueError, match="unknown source_type"):
        _source(source_type="stock_price")


def test_rejects_blank_citation_inv_15():
    with pytest.raises(ValueError, match="citation"):
        _source(citation="  ")


def test_rejects_blank_value():
    with pytest.raises(ValueError, match="value"):
        _source(value=" ")


def test_effective_to_defaults_to_none():
    source = _source()
    assert source.effective_to is None
