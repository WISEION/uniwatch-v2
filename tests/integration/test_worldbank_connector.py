"""INT-01, INT-02, FR-TND-10: raw evidence is saved unconditionally before
the drift check; a drift-free page produces one Signal per project;
a drifted page still keeps its raw evidence, blocks signal storage, and
raises SchemaDriftDetected."""

from __future__ import annotations

import json

import pytest
from source_fixtures import WORLDBANK_FIXTURES

from packages.tender.raw_snapshot import get_raw_snapshot
from packages.tender.schema_drift import SchemaDriftDetected
from packages.tender.signals_store import list_signals
from packages.tender.worldbank_connector import ingest_donor_pipeline_page


async def test_ingest_real_page_os0_stores_ten_signals(engine):
    raw_body = (WORLDBANK_FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes()
    payload = json.loads(raw_body)
    async with engine.begin() as conn:
        signal_ids = await ingest_donor_pipeline_page(
            conn,
            raw_body=raw_body,
            payload=payload,
            os_=0,
            correlation_id="corr-worldbank-1",
            observed_at="2026-08-05T12:00:00+00:00",
        )
        assert len(signal_ids) == len(payload["projects"])

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        stored_project_ids = {row["value"]["project_id"] for row in rows}
        assert stored_project_ids == set(payload["projects"].keys())


async def test_page_level_drift_saves_evidence_and_raises(engine):
    raw_body = (WORLDBANK_FIXTURES / "az_donor_pipeline_page_os0.raw.json").read_bytes()
    payload = json.loads(raw_body)
    drifted_payload = {**payload, "unexpected_new_field": "drift"}  # source adds a field the frozen contract never declared

    async with engine.begin() as conn:
        with pytest.raises(SchemaDriftDetected) as exc_info:
            await ingest_donor_pipeline_page(
                conn,
                raw_body=raw_body,  # raw bytes still reflect the real, undrifted capture
                payload=drifted_payload,
                os_=0,
                correlation_id="corr-worldbank-drift",
                observed_at="2026-08-05T12:00:00+00:00",
            )
        assert "unexpected_new_field" in exc_info.value.drift.added_fields

        rows = await list_signals(conn, signal_type="donor_pipeline_project")
        assert rows == []  # drift blocked signal storage, but evidence below was still saved

        snapshot = await get_raw_snapshot(conn, exc_info.value.raw_snapshot_id)
        assert "unexpected_new_field" not in snapshot.body  # raw evidence preserved exactly as captured, not the synthetic drift
