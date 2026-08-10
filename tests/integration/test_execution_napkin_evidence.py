from __future__ import annotations

import pytest

from packages.decision.execution_napkin_evidence import get_execution_napkin_evidence, save_execution_napkin_evidence
from packages.tender.normalized import get_or_create_tender


async def test_save_and_get_roundtrips_raw_bytes(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-evidence-1")
        evidence_id = await save_execution_napkin_evidence(
            conn,
            tender_id=tender_id,
            capture_kind="photo",
            raw_bytes=b"fake-jpeg-bytes",
            mime_type="image/jpeg",
            correlation_id="test-4c-evidence-1",
        )
        evidence = await get_execution_napkin_evidence(conn, evidence_id)

    assert evidence.tender_id == tender_id
    assert evidence.capture_kind == "photo"
    assert evidence.raw_bytes == b"fake-jpeg-bytes"
    assert evidence.checksum == __import__("hashlib").sha256(b"fake-jpeg-bytes").hexdigest()


async def test_voice_capture_kind_is_accepted(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-evidence-2")
        evidence_id = await save_execution_napkin_evidence(
            conn,
            tender_id=tender_id,
            capture_kind="voice",
            raw_bytes=b"fake-audio-bytes",
            mime_type="audio/ogg",
            correlation_id="test-4c-evidence-2",
        )
        evidence = await get_execution_napkin_evidence(conn, evidence_id)
    assert evidence.capture_kind == "voice"


async def test_a_recapture_inserts_a_new_row_not_an_update(engine):
    async with engine.begin() as conn:
        tender_id = await get_or_create_tender(conn, source="etender", identity_key="test-4c-evidence-3")
        first_id = await save_execution_napkin_evidence(
            conn, tender_id=tender_id, capture_kind="photo", raw_bytes=b"v1", mime_type="image/jpeg", correlation_id="c1"
        )
        second_id = await save_execution_napkin_evidence(
            conn, tender_id=tender_id, capture_kind="photo", raw_bytes=b"v2", mime_type="image/jpeg", correlation_id="c2"
        )
    assert first_id != second_id
