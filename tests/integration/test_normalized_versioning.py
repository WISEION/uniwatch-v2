"""FR-TND-02, P108: normalized facts are immutable versions that keep a
provenance link to their raw snapshot; a changed tender gets a new
version, the old one stays intact (P108: v1 changes were invisible to
history because details/BOM overwrote in place with COALESCE)."""

from __future__ import annotations

from packages.tender.normalized import create_normalized_version, get_current_tender_version_id, get_or_create_tender
from packages.tender.raw_snapshot import save_raw_snapshot


async def _snapshot(conn, body: bytes) -> int:
    return await save_raw_snapshot(
        conn,
        source="etender",
        resource_type="etender.event_details",
        identity_key="etender.event_details|id=355920",
        raw_body=body,
        contract_version="etender.event_details",
        correlation_id="corr-1",
    )


async def test_get_or_create_tender_is_idempotent_per_identity(engine):
    async with engine.begin() as conn:
        id1 = await get_or_create_tender(conn, source="etender", identity_key="etender.event_details|id=355920")
    async with engine.begin() as conn:
        id2 = await get_or_create_tender(conn, source="etender", identity_key="etender.event_details|id=355920")
    assert id1 == id2


async def test_second_normalization_creates_a_new_version_not_an_overwrite(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="etender.event_details|id=355920")
        snap1 = await _snapshot(conn, b'{"id": 355920, "estimatedAmount": 16922253.74}')
        snap2 = await _snapshot(conn, b'{"id": 355920, "estimatedAmount": 17000000.00}')

        v1 = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snap1,
            parser_version="etender-v1",
            normalized_fields={"estimated_amount": 16922253.74},
        )
        v2 = await create_normalized_version(
            conn,
            tender_id=tender_id,
            raw_snapshot_id=snap2,
            parser_version="etender-v1",
            normalized_fields={"estimated_amount": 17000000.00},
        )

    assert v1.version_number == 1
    assert v2.version_number == 2
    # P108: the first version's own data is untouched by the second insert.
    assert v1.normalized_fields == {"estimated_amount": 16922253.74}
    assert v1.raw_snapshot_id == snap1
    assert v2.raw_snapshot_id == snap2


async def test_get_current_tender_version_id_returns_the_current_version(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-event-4a-version")
        snap = await _snapshot(conn, b'{"eventId": 999002}')
        version = await create_normalized_version(
            conn, tender_id=tender_id, raw_snapshot_id=snap, parser_version="v1", normalized_fields={}
        )
        current_version_id = await get_current_tender_version_id(conn, tender_id=tender_id)

    assert current_version_id == version.id


async def test_get_current_tender_version_id_returns_none_for_unknown_tender(engine):
    async with engine.begin() as conn:
        result = await get_current_tender_version_id(conn, tender_id=999999999)

    assert result is None
