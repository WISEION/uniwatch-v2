"""DM-02/DM-03 for vendor napkin evidence (task 3.A, P312/P313): raw
photo/voice bytes are immutable and checksummed; a re-capture is always a
new row. Same discipline as tests/integration/test_raw_snapshot.py for
packages/tender's raw_snapshots table."""

from __future__ import annotations

from packages.vendor.napkin_evidence import checksum_of, get_napkin_evidence, save_napkin_evidence


async def test_save_napkin_evidence_stores_checksummed_bytes(engine):
    raw_bytes = b"\xff\xd8\xff\xe0-fake-jpeg-bytes-for-a-test"
    async with engine.begin() as conn:
        evidence_id = await save_napkin_evidence(
            conn,
            capture_kind="photo",
            raw_bytes=raw_bytes,
            mime_type="image/jpeg",
            correlation_id="corr-1",
        )

    async with engine.begin() as conn:
        evidence = await get_napkin_evidence(conn, evidence_id)

    assert evidence.checksum == checksum_of(raw_bytes)
    assert evidence.raw_bytes == raw_bytes
    assert evidence.capture_kind == "photo"
    assert evidence.mime_type == "image/jpeg"


async def test_recapture_creates_a_new_row_not_an_update(engine):
    bytes_v1 = b"first-capture-bytes"
    bytes_v2 = b"second-capture-bytes-different-content"

    async with engine.begin() as conn:
        id1 = await save_napkin_evidence(
            conn, capture_kind="photo", raw_bytes=bytes_v1, mime_type="image/jpeg", correlation_id="corr-1"
        )
    async with engine.begin() as conn:
        id2 = await save_napkin_evidence(
            conn, capture_kind="photo", raw_bytes=bytes_v2, mime_type="image/jpeg", correlation_id="corr-2"
        )

    assert id1 != id2
    async with engine.begin() as conn:
        first_still_intact = await get_napkin_evidence(conn, id1)
    assert first_still_intact.checksum == checksum_of(bytes_v1)


async def test_voice_capture_kind_is_accepted(engine):
    raw_bytes = b"fake-voice-note-bytes"
    async with engine.begin() as conn:
        evidence_id = await save_napkin_evidence(
            conn, capture_kind="voice", raw_bytes=raw_bytes, mime_type="audio/wav", correlation_id="corr-3"
        )

    async with engine.begin() as conn:
        evidence = await get_napkin_evidence(conn, evidence_id)

    assert evidence.capture_kind == "voice"
