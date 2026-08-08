"""Normalized fact versioning (FR-TND-02, DM-01..03, P108): every call
creates a new immutable tender_versions row — never an UPDATE of a
previous version. `tenders` holds only the identity anchor and a pointer
to the current version (DM-01: one authoritative entity for "what's
current", not a second mutable copy of version content)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


@dataclass(frozen=True)
class TenderVersion:
    id: int
    tender_id: int
    version_number: int
    raw_snapshot_id: int
    parser_version: str
    normalized_fields: dict[str, Any]


async def get_or_create_tender(conn: AsyncConnection, *, source: str, identity_key: str) -> int:
    existing = (
        (
            await conn.execute(
                text("SELECT id FROM tenders WHERE source = :source AND identity_key = :identity_key"),
                {"source": source, "identity_key": identity_key},
            )
        )
        .mappings()
        .first()
    )
    if existing is not None:
        return existing["id"]
    return (
        await conn.execute(
            text("INSERT INTO tenders (source, identity_key) VALUES (:source, :identity_key) RETURNING id"),
            {"source": source, "identity_key": identity_key},
        )
    ).scalar_one()


async def get_current_tender_version_id(conn: AsyncConnection, *, tender_id: int) -> int | None:
    row = (await conn.execute(text("SELECT current_version_id FROM tenders WHERE id = :id"), {"id": tender_id})).first()
    if row is None:
        return None
    return row[0]


async def create_normalized_version(
    conn: AsyncConnection,
    *,
    tender_id: int,
    raw_snapshot_id: int,
    parser_version: str,
    normalized_fields: dict[str, Any],
) -> TenderVersion:
    next_version = (
        (
            await conn.execute(
                text("SELECT COALESCE(MAX(version_number), 0) + 1 AS n FROM tender_versions WHERE tender_id = :tender_id"),
                {"tender_id": tender_id},
            )
        )
        .mappings()
        .one()["n"]
    )

    version_id = (
        await conn.execute(
            text(
                """
                INSERT INTO tender_versions
                    (tender_id, version_number, raw_snapshot_id, parser_version, normalized_fields)
                VALUES (:tender_id, :version_number, :raw_snapshot_id, :parser_version,
                        CAST(:normalized_fields AS jsonb))
                RETURNING id
                """
            ),
            {
                "tender_id": tender_id,
                "version_number": next_version,
                "raw_snapshot_id": raw_snapshot_id,
                "parser_version": parser_version,
                "normalized_fields": json.dumps(normalized_fields),
            },
        )
    ).scalar_one()

    await conn.execute(
        text("UPDATE tenders SET current_version_id = :version_id WHERE id = :tender_id"),
        {"version_id": version_id, "tender_id": tender_id},
    )

    return TenderVersion(
        id=version_id,
        tender_id=tender_id,
        version_number=next_version,
        raw_snapshot_id=raw_snapshot_id,
        parser_version=parser_version,
        normalized_fields=normalized_fields,
    )
