"""DM-02/DM-03: raw evidence is immutable and checksummed; a re-fetch is
always a new row."""

from __future__ import annotations

from packages.tender.raw_snapshot import checksum_of, get_raw_snapshot, save_raw_snapshot


async def test_save_raw_snapshot_stores_checksummed_body(engine):
    raw_body = b'{"id": 355920, "eventType": 7}'
    async with engine.begin() as conn:
        snapshot_id = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="etender.event_details|id=355920",
            raw_body=raw_body,
            contract_version="etender.event_details",
            correlation_id="corr-1",
        )

    async with engine.begin() as conn:
        snapshot = await get_raw_snapshot(conn, snapshot_id)

    assert snapshot.checksum == checksum_of(raw_body)
    assert snapshot.body == {"id": 355920, "eventType": 7}
    assert snapshot.source == "etender"


async def test_refetch_creates_a_new_row_not_an_update(engine):
    body_v1 = b'{"id": 355920, "eventType": 7}'
    body_v2 = b'{"id": 355920, "eventType": 7, "estimatedAmount": 16922253.74}'

    async with engine.begin() as conn:
        id1 = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="etender.event_details|id=355920",
            raw_body=body_v1,
            contract_version="etender.event_details",
            correlation_id="corr-1",
        )
    async with engine.begin() as conn:
        id2 = await save_raw_snapshot(
            conn,
            source="etender",
            resource_type="etender.event_details",
            identity_key="etender.event_details|id=355920",
            raw_body=body_v2,
            contract_version="etender.event_details",
            correlation_id="corr-2",
        )

    assert id1 != id2
    async with engine.begin() as conn:
        first_still_intact = await get_raw_snapshot(conn, id1)
    assert first_still_intact.checksum == checksum_of(body_v1)
