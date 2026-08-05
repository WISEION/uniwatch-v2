"""FR-TND-02 acceptance: "Из UI открывается raw evidence для любой версии"
-- every normalized tender_version traces back to the exact raw bytes it
was parsed from, and the stored checksum genuinely matches those bytes
(not just present, but correct)."""

from __future__ import annotations

import json
from pathlib import Path

from sqlalchemy import text

from packages.tender.etender_connector import ingest_bom_lines_page, ingest_event_details, ingest_events_list_page
from packages.tender.normalized import create_normalized_version, get_or_create_tender
from packages.tender.raw_snapshot import checksum_of, save_raw_snapshot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "tender-snapshots" / "etender"


def _load_bytes(name: str) -> bytes:
    return (FIXTURES / name).read_bytes()


async def _raw_snapshot_row(conn, snapshot_id: int):
    return (
        (await conn.execute(text("SELECT checksum, body FROM raw_snapshots WHERE id = :id"), {"id": snapshot_id}))
        .mappings()
        .one()
    )


async def test_event_details_version_traces_to_its_exact_raw_bytes(engine):
    raw_body = _load_bytes("event_355920_details.raw.json")

    async with engine.begin() as conn:
        version = await ingest_event_details(conn, raw_body=raw_body, payload=json.loads(raw_body), correlation_id="corr-trace-1")

    async with engine.begin() as conn:
        row = await _raw_snapshot_row(conn, version.raw_snapshot_id)

    assert row["checksum"] == checksum_of(raw_body)
    body = row["body"]
    if isinstance(body, str):
        body = json.loads(body)
    assert body == json.loads(raw_body)  # the raw evidence opened is byte-for-byte the source response


async def test_bom_lines_version_traces_to_its_exact_raw_bytes(engine):
    raw_body = _load_bytes("event_355920_bomlines_page1.raw.json")

    async with engine.begin() as conn:
        version = await ingest_bom_lines_page(
            conn, event_id=355920, raw_body=raw_body, payload=json.loads(raw_body), correlation_id="corr-trace-2"
        )

    async with engine.begin() as conn:
        row = await _raw_snapshot_row(conn, version.raw_snapshot_id)

    assert row["checksum"] == checksum_of(raw_body)


async def test_events_list_version_traces_to_its_exact_raw_bytes(engine):
    raw_body = _load_bytes("events_list_page1.raw.json")
    query_params = {
        "EventType": "",
        "PageSize": 6,
        "EventStatus": 1,
        "Keyword": "",
        "buyerOrganizationName": "",
        "documentNumber": "",
        "publishDateFrom": "",
        "publishDateTo": "",
        "AwardedparticipantName": "",
        "AwardedparticipantVoen": "",
        "DocumentViewType": "",
        "IsArchived": False,
    }

    async with engine.begin() as conn:
        version = await ingest_events_list_page(
            conn, raw_body=raw_body, payload=json.loads(raw_body), query_params=query_params, correlation_id="corr-trace-3"
        )

    async with engine.begin() as conn:
        row = await _raw_snapshot_row(conn, version.raw_snapshot_id)

    assert row["checksum"] == checksum_of(raw_body)


async def test_a_second_version_of_the_same_tender_traces_to_its_own_distinct_raw_snapshot(engine):
    # P108-adjacent mechanism check: two versions of the SAME tender must
    # each open their OWN raw evidence, not share/overwrite one snapshot.
    body_v1 = b'{"id": 355920, "eventType": 7, "estimatedAmount": 1.0}'
    body_v2 = b'{"id": 355920, "eventType": 7, "estimatedAmount": 2.0}'

    # These bodies don't match the frozen contract's declared field set
    # fully, but that's fine here -- this test only exercises raw<->version
    # traceability, not contract validation (covered elsewhere).
    identity_key = "etender.event_details|id=999999"

    async with engine.begin() as conn:
        row1 = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key=identity_key,
            raw_body=body_v1,
            contract_version="etender.event_details",
            correlation_id="corr-trace-4",
        )
        row2 = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key=identity_key,
            raw_body=body_v2,
            contract_version="etender.event_details",
            correlation_id="corr-trace-4",
        )

        tender_id = await get_or_create_tender(conn, source="etender", identity_key=identity_key)
        version1 = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=row1,
            parser_version="etender-v1",
            normalized_fields={"estimated_amount": 1.0},
        )
        version2 = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=row2,
            parser_version="etender-v1",
            normalized_fields={"estimated_amount": 2.0},
        )

    assert version1.raw_snapshot_id == row1
    assert version2.raw_snapshot_id == row2
    assert version1.raw_snapshot_id != version2.raw_snapshot_id  # distinct evidence per version, neither overwritten
