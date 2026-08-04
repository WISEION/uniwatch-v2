"""Raw immutable evidence (DM-02, DM-03): a re-fetch always creates a new
row; application code never issues an UPDATE against raw_snapshots. The
checksum is sha256 of the exact raw bytes captured, so raw evidence is
provably unmodified end-to-end (docs/adr/0003-data-authority-and-provenance.md)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class RawSnapshot:
    id: int
    source: str
    resource_type: str
    identity_key: str
    checksum: str
    body: dict[str, Any]
    contract_version: str
    correlation_id: str


def checksum_of(raw_body: bytes) -> str:
    return hashlib.sha256(raw_body).hexdigest()


async def save_raw_snapshot(
    conn: AsyncConnection,
    *,
    source: str,
    resource_type: str,
    identity_key: str,
    raw_body: bytes,
    contract_version: str,
    correlation_id: str,
) -> int:
    return (
        await conn.execute(
            text(
                """
                INSERT INTO raw_snapshots
                    (source, resource_type, identity_key, checksum, body, contract_version, correlation_id)
                VALUES (:source, :resource_type, :identity_key, :checksum, CAST(:body AS jsonb),
                        :contract_version, :correlation_id)
                RETURNING id
                """
            ),
            {
                "source": source,
                "resource_type": resource_type,
                "identity_key": identity_key,
                "checksum": checksum_of(raw_body),
                "body": raw_body.decode("utf-8"),
                "contract_version": contract_version,
                "correlation_id": correlation_id,
            },
        )
    ).scalar_one()


async def get_raw_snapshot(conn: AsyncConnection, snapshot_id: int) -> RawSnapshot:
    row = (
        (
            await conn.execute(
                text(
                    """
                    SELECT id, source, resource_type, identity_key, checksum, body,
                           contract_version, correlation_id
                    FROM raw_snapshots WHERE id = :id
                    """
                ),
                {"id": snapshot_id},
            )
        )
        .mappings()
        .one()
    )
    body = row["body"]
    if isinstance(body, str):
        body = json.loads(body)
    return RawSnapshot(
        id=row["id"],
        source=row["source"],
        resource_type=row["resource_type"],
        identity_key=row["identity_key"],
        checksum=row["checksum"],
        body=body,
        contract_version=row["contract_version"],
        correlation_id=row["correlation_id"],
    )
