"""Integration tests for the official-source registry (Phase 5, task 5.A,
FR-ALG-23). No real law/FX/VAT/price-index value appears here -- every
example below is explicitly synthetic test fixture data."""

from __future__ import annotations

from packages.algorithm.official_source_registry_model import OfficialSource
from packages.algorithm.official_source_registry_store import (
    get_effective_source,
    list_sources_by_type,
    store_official_source,
)


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


async def test_store_and_list_by_type(engine):
    async with engine.begin() as conn:
        await store_official_source(conn, _source())
        sources = await list_sources_by_type(conn, source_type="fx_rate")

    assert len(sources) == 1
    assert sources[0]["name"] == "USD/AZN"
    assert sources[0]["value"] == "1.0000"


async def test_get_effective_source_picks_the_row_covering_as_of_date(engine):
    async with engine.begin() as conn:
        await store_official_source(
            conn, _source(value="1.0000", effective_from="2026-01-01T00:00:00+00:00", effective_to="2026-06-01T00:00:00+00:00")
        )
        await store_official_source(conn, _source(value="1.1000", effective_from="2026-06-01T00:00:00+00:00"))

        before = await get_effective_source(conn, source_type="fx_rate", name="USD/AZN", as_of="2026-03-01T00:00:00+00:00")
        after = await get_effective_source(conn, source_type="fx_rate", name="USD/AZN", as_of="2026-08-12T00:00:00+00:00")

    assert before["value"] == "1.0000"
    assert after["value"] == "1.1000"


async def test_get_effective_source_returns_none_before_any_effective_date(engine):
    async with engine.begin() as conn:
        await store_official_source(conn, _source(effective_from="2026-06-01T00:00:00+00:00"))
        result = await get_effective_source(conn, source_type="fx_rate", name="USD/AZN", as_of="2026-01-01T00:00:00+00:00")
    assert result is None


async def test_superseding_a_rate_never_edits_the_old_row(engine):
    async with engine.begin() as conn:
        await store_official_source(
            conn, _source(value="1.0000", effective_from="2026-01-01T00:00:00+00:00", effective_to="2026-06-01T00:00:00+00:00")
        )
        await store_official_source(conn, _source(value="1.1000", effective_from="2026-06-01T00:00:00+00:00"))
        all_rows = await list_sources_by_type(conn, source_type="fx_rate")

    assert len(all_rows) == 2
    assert {row["value"] for row in all_rows} == {"1.0000", "1.1000"}
