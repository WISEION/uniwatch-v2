"""End-to-end: real captured fixture -> raw snapshot -> normalized version,
and a synthetically-drifted copy of that same real fixture -> raw snapshot
still saved, normalization blocked, schema_drift_event enqueued (FR-TND-10).

`SchemaDriftDetected` is a control-flow signal for the caller (the worker
job loop, later), not a reason to abort the whole DB transaction — a
caller catches it and lets the transaction commit, so the raw evidence and
the drift event it already wrote are not thrown away just because
normalization didn't happen. These tests catch it the same way."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from packages.tender.etender_connector import SchemaDriftDetected, ingest_event_details
from packages.tender.etender_contract import EVENT_DETAILS_CONTRACT

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


async def test_ingest_real_fixture_creates_raw_snapshot_and_normalized_version(engine):
    raw_body = _load_bytes("event_355920_details.raw.json")
    payload = json.loads(raw_body)

    async with engine.begin() as conn:
        version = await ingest_event_details(
            conn,
            contract=EVENT_DETAILS_CONTRACT,
            raw_body=raw_body,
            payload=payload,
            correlation_id="corr-real-1",
        )

    assert version.version_number == 1
    # FR-TND-10: the actual response value is used, never a requested filter value.
    assert version.normalized_fields["event_type_actual"] == 7
    assert version.normalized_fields["organization_voen"] == "1000418451"

    async with engine.begin() as conn:
        row = (
            (await conn.execute(text("SELECT checksum FROM raw_snapshots WHERE id = :id"), {"id": version.raw_snapshot_id}))
            .mappings()
            .one()
        )
    assert row["checksum"] is not None


async def test_schema_drift_blocks_normalization_but_still_saves_raw_evidence(engine):
    raw_body = _load_bytes("event_355920_details.raw.json")
    payload = json.loads(raw_body)
    drifted_payload = {**payload}
    del drifted_payload["eventType"]  # simulate the source silently dropping a field

    async with engine.begin() as conn:
        try:
            await ingest_event_details(
                conn,
                contract=EVENT_DETAILS_CONTRACT,
                raw_body=raw_body,  # raw bytes still reflect the real, undrifted capture
                payload=drifted_payload,
                correlation_id="corr-drift-1",
            )
            raised = False
        except SchemaDriftDetected:
            raised = True
    assert raised is True

    async with engine.begin() as conn:
        # Raw evidence was still captured even though normalization was blocked.
        snapshot_count = (
            (await conn.execute(text("SELECT count(*) AS n FROM raw_snapshots WHERE correlation_id = 'corr-drift-1'")))
            .mappings()
            .one()["n"]
        )
        assert snapshot_count == 1

        # No normalized version was created for the drifted response.
        tender_count = (
            (await conn.execute(text("SELECT count(*) AS n FROM tenders WHERE identity_key = 'etender.event_details|id=355920'")))
            .mappings()
            .one()["n"]
        )
        assert tender_count == 0

        drift_events = (
            (await conn.execute(text("SELECT payload FROM outbox WHERE event_type = 'schema_drift_event'"))).mappings().all()
        )
        assert len(drift_events) == 1
