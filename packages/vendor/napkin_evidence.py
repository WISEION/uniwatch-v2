"""Raw immutable napkin-ingestion evidence (DM-02, DM-03, task 3.A,
P312/P313): a re-capture always creates a new row; application code never
issues an UPDATE against vendor_napkin_evidence. checksum is sha256 of the
exact raw bytes captured, same provenance discipline as
packages/tender/raw_snapshot.py -- kept as a separate module/table (not a
reuse of raw_snapshot.py) because packages/vendor must never import from
packages/tender (ADR-0001 domain boundary) and the payload shape differs
(raw binary bytes here, JSON there)."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class NapkinEvidence:
    id: int
    capture_kind: str
    mime_type: str
    checksum: str
    raw_bytes: bytes
    correlation_id: str


def checksum_of(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


async def save_napkin_evidence(
    conn: AsyncConnection,
    *,
    capture_kind: str,
    raw_bytes: bytes,
    mime_type: str,
    correlation_id: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO vendor_napkin_evidence
                    (capture_kind, mime_type, checksum, raw_bytes, correlation_id)
                VALUES (:capture_kind, :mime_type, :checksum, :raw_bytes, :correlation_id)
                RETURNING id
                """
            ),
            {
                "capture_kind": capture_kind,
                "mime_type": mime_type,
                "checksum": checksum_of(raw_bytes),
                "raw_bytes": raw_bytes,
                "correlation_id": correlation_id,
            },
        )
    ).scalar_one()


async def get_napkin_evidence(conn: AsyncConnection, evidence_id: int) -> NapkinEvidence:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, capture_kind, mime_type, checksum, raw_bytes, correlation_id
                    FROM vendor_napkin_evidence WHERE id = :id
                    """
                ),
                {"id": evidence_id},
            )
        )
        .mappings()
        .one()
    )
    return NapkinEvidence(
        id=row["id"],
        capture_kind=row["capture_kind"],
        mime_type=row["mime_type"],
        checksum=row["checksum"],
        raw_bytes=bytes(row["raw_bytes"]),
        correlation_id=row["correlation_id"],
    )
