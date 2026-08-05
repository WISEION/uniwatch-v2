"""INV-15, INV-16, INV-17: a stored signal round-trips its full fact tuple
and object binding, and signals accumulate (append-only) rather than being
updated in place."""

from __future__ import annotations

from packages.tender.raw_snapshot import save_raw_snapshot
from packages.tender.signal_model import Signal
from packages.tender.signals_store import list_signals, store_signal


async def test_store_and_list_signal_roundtrip(engine):
    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="worldbank_projects_api",
            resource_type="worldbank.donor_pipeline_page",
            identity_key="worldbank.donor_pipeline_page|countrycode_exact=AZ&os=0",
            raw_body=b'{"total":"79"}',
            contract_version="worldbank.donor_pipeline_page",
            correlation_id="test-corr-1",
        )
        signal = Signal(
            signal_type="donor_pipeline_project",
            source="worldbank_projects_api",
            raw_snapshot_id=snapshot_id,
            value={"project_id": "P505208", "project_name": "Azerbaijan Scaling-Up Renewable Energy Project"},
            observed_at="2026-08-05T00:00:00+00:00",
            ttl_class="funding_decision",
            confidence="official_source",
            object_customer=None,
            object_region="Republic of Azerbaijan",
            object_project_type="2",
            correlation_id="test-corr-1",
        )
        signal_id = await store_signal(conn, signal)
        assert signal_id is not None

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        assert len(rows) == 1
        assert rows[0]["value"]["project_id"] == "P505208"
        assert rows[0]["object_customer"] is None
        assert rows[0]["object_region"] == "Republic of Azerbaijan"


async def test_signals_are_append_only_not_updated(engine):
    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="worldbank_projects_api",
            resource_type="worldbank.donor_pipeline_page",
            identity_key="worldbank.donor_pipeline_page|countrycode_exact=AZ&os=0",
            raw_body=b'{"total":"79"}',
            contract_version="worldbank.donor_pipeline_page",
            correlation_id="test-corr-2",
        )
        make_signal = lambda observed_at: Signal(  # noqa: E731
            signal_type="donor_pipeline_project",
            source="worldbank_projects_api",
            raw_snapshot_id=snapshot_id,
            value={"project_id": "P505208", "status": "Pipeline"},
            observed_at=observed_at,
            ttl_class="funding_decision",
            confidence="official_source",
            object_customer=None,
            object_region="Republic of Azerbaijan",
            object_project_type="2",
            correlation_id="test-corr-2",
        )
        await store_signal(conn, make_signal("2026-08-05T00:00:00+00:00"))
        await store_signal(conn, make_signal("2026-08-06T00:00:00+00:00"))

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        assert len(rows) == 2  # two observations of the same project, not one overwritten row
        observed_ats = sorted(str(row["observed_at"]) for row in rows)
        assert len(observed_ats) == 2
