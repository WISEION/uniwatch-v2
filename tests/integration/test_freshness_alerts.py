"""Source-freshness alert (Phase 6, task 6.C, NFR-OPS-02). Fires only on
"never fetched", a boolean condition -- not a staleness window, since
D-SLO/TBD-01/TBD-02 remain open (AGENTS.md hard ban #2)."""

from __future__ import annotations

from packages.tender.freshness_alerts import source_never_succeeded
from packages.tender.raw_snapshot import save_raw_snapshot


async def test_fires_when_no_source_has_ever_fetched(engine):
    async with engine.connect() as conn:
        result = await source_never_succeeded(conn)
    assert result.firing is True
    assert "etender" in result.detail
    assert "worldbank_projects_api" in result.detail


async def test_does_not_fire_once_every_known_source_has_fetched(engine):
    async with engine.begin() as conn:
        await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="design_tender",
            identity_key="fresh-1",
            raw_body=b'{"a": 1}',
            contract_version="v1",
            correlation_id="corr-fresh-1",
        )
        await save_raw_snapshot(
            conn,
            source="worldbank_projects_api",
            resource_type="project",
            identity_key="fresh-2",
            raw_body=b'{"b": 2}',
            contract_version="v1",
            correlation_id="corr-fresh-2",
        )
        result = await source_never_succeeded(conn)
    assert result.firing is False
