"""FR-TND-07, P109: each subresource (details, BOQ) has an independent
status; an enrichment failure on one never looks like success, and never
gets masked by another subresource's success."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from packages.tender.etender_connector import SchemaDriftDetected, ingest_bom_lines_page, ingest_event_details

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


async def test_boq_ingestion_failure_does_not_affect_successful_details_ingestion(engine):
    details_body = _load_bytes("event_355920_details.raw.json")

    async with engine.begin() as conn:
        details_version = await ingest_event_details(
            conn, raw_body=details_body, payload=json.loads(details_body), correlation_id="corr-indep-1"
        )

    bom_body = _load_bytes("event_355920_bomlines_page1.raw.json")
    bom_payload = json.loads(bom_body)
    del bom_payload["totalItems"]  # simulate a drifted/broken BOQ page response

    async with engine.begin() as conn:
        try:
            await ingest_bom_lines_page(
                conn, event_id=355920, raw_body=bom_body, payload=bom_payload, correlation_id="corr-indep-1"
            )
            raised = False
        except SchemaDriftDetected:
            raised = True
    assert raised is True

    # The details ingestion that already succeeded is completely unaffected
    # -- its version and raw snapshot are still there, untouched.
    async with engine.begin() as conn:
        row = (
            (
                await conn.execute(
                    text("SELECT normalized_fields FROM tender_versions WHERE id = :id"),
                    {"id": details_version.id},
                )
            )
            .mappings()
            .one()
        )
    normalized_fields = row["normalized_fields"]
    if isinstance(normalized_fields, str):
        normalized_fields = json.loads(normalized_fields)
    assert normalized_fields["event_type_actual"] == 7

    # No BOQ import row was ever created for event 355920 by the failed
    # attempt -- the failure is visibly absent, not silently "0 fetched, all
    # good".
    async with engine.begin() as conn:
        boq_row = (
            (await conn.execute(text("SELECT status FROM boq_import WHERE event_id = 355920 AND source = 'etender'")))
            .mappings()
            .first()
        )
    assert boq_row is None


async def test_successful_boq_ingestion_does_not_require_or_touch_details_ingestion(engine):
    # The reverse direction: BOQ can be fully ingested for an event whose
    # details were never fetched in this session -- subresources are
    # genuinely independent, neither is a prerequisite in the data model.
    bom_body = _load_bytes("event_355920_bomlines_page1.raw.json")

    async with engine.begin() as conn:
        version = await ingest_bom_lines_page(
            conn, event_id=355920, raw_body=bom_body, payload=json.loads(bom_body), correlation_id="corr-indep-2"
        )

    assert version.normalized_fields["total_items"] == 4135

    async with engine.begin() as conn:
        details_count = (
            (await conn.execute(text("SELECT count(*) AS n FROM tenders WHERE identity_key = 'etender.event_details|id=355920'")))
            .mappings()
            .one()["n"]
        )
    assert details_count == 0
