"""Raw immutable execution-ledger napkin-ingestion evidence (Phase 4, task
4.C, INV-18, ADR-0003 layer 1). A re-capture always creates a new row;
application code never issues an UPDATE against execution_napkin_evidence.
checksum is sha256 of the exact raw bytes captured -- same provenance
discipline as packages/tender/raw_snapshot.py and
packages/vendor/napkin_evidence.py, kept as its own table (not a reuse of
either) because this is tender-scoped from capture time and packages/decision
must never share a table with packages/vendor across the ADR-0001 domain
boundary."""

from __future__ import annotations

import hashlib
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class ExecutionNapkinEvidence:
    id: int
    tender_id: int
    capture_kind: str
    mime_type: str
    checksum: str
    raw_bytes: bytes
    correlation_id: str


def checksum_of(raw_bytes: bytes) -> str:
    return hashlib.sha256(raw_bytes).hexdigest()


async def save_execution_napkin_evidence(
    conn: AsyncConnection,
    *,
    tender_id: int,
    capture_kind: str,
    raw_bytes: bytes,
    mime_type: str,
    correlation_id: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO execution_napkin_evidence
                    (tender_id, capture_kind, mime_type, checksum, raw_bytes, correlation_id)
                VALUES (:tender_id, :capture_kind, :mime_type, :checksum, :raw_bytes, :correlation_id)
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "capture_kind": capture_kind,
                "mime_type": mime_type,
                "checksum": checksum_of(raw_bytes),
                "raw_bytes": raw_bytes,
                "correlation_id": correlation_id,
            },
        )
    ).scalar_one()


async def get_execution_napkin_evidence(conn: AsyncConnection, evidence_id: int) -> ExecutionNapkinEvidence:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, tender_id, capture_kind, mime_type, checksum, raw_bytes, correlation_id
                    FROM execution_napkin_evidence WHERE id = :id
                    """
                ),
                {"id": evidence_id},
            )
        )
        .mappings()
        .one()
    )
    return ExecutionNapkinEvidence(
        id=row["id"],
        tender_id=row["tender_id"],
        capture_kind=row["capture_kind"],
        mime_type=row["mime_type"],
        checksum=row["checksum"],
        raw_bytes=bytes(row["raw_bytes"]),
        correlation_id=row["correlation_id"],
    )
