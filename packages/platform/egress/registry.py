"""Trusted source registry (NFR-SEC-03, threat model T2,
docs/architecture/egress-validator-contract.md §1). A host must be
explicitly registered and promoted to `trusted` by an actual scanner run
before any outbound request is permitted to it -- a structural check
(scheme/status-code) alone is not sufficient (the ADB/0.18.0 lesson).
Revocation is append-only metadata on the same row, never a delete (same
discipline as `packages/platform/rbac` disable-not-delete)."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection

_COLUMNS = """id, host, allowed_schemes, status, scanner_run_reference,
              registered_by, revoked_reason"""


@dataclass(frozen=True)
class TrustedSource:
    id: int
    host: str
    allowed_schemes: tuple[str, ...]
    status: str
    scanner_run_reference: str | None
    registered_by: str
    revoked_reason: str | None


def _row_to_source(row) -> TrustedSource:
    return TrustedSource(
        id=row["id"],
        host=row["host"],
        allowed_schemes=tuple(row["allowed_schemes"]),
        status=row["status"],
        scanner_run_reference=row["scanner_run_reference"],
        registered_by=row["registered_by"],
        revoked_reason=row["revoked_reason"],
    )


async def register_source(
    conn: AsyncConnection,
    *,
    host: str,
    allowed_schemes: list[str],
    registered_by: str,
) -> TrustedSource:
    """Registers a new source in `pending_scan` -- never `trusted` on
    creation; promotion requires an explicit scanner run (`promote_to_trusted`)."""
    row = (
        (
            await conn.execute(
                text(
                    f"""
                    INSERT INTO trusted_sources (host, allowed_schemes, registered_by)
                    VALUES (:host, :allowed_schemes, :registered_by)
                    RETURNING {_COLUMNS}
                    """
                ),
                {"host": host, "allowed_schemes": allowed_schemes, "registered_by": registered_by},
            )
        )
        .mappings()
        .one()
    )
    return _row_to_source(row)


async def promote_to_trusted(conn: AsyncConnection, *, host: str, scanner_run_reference: str) -> TrustedSource:
    row = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE trusted_sources
                    SET status = 'trusted', scanner_run_reference = :scanner_run_reference, promoted_at = now()
                    WHERE host = :host
                    RETURNING {_COLUMNS}
                    """
                ),
                {"host": host, "scanner_run_reference": scanner_run_reference},
            )
        )
        .mappings()
        .one()
    )
    return _row_to_source(row)


async def revoke_source(conn: AsyncConnection, *, host: str, reason: str) -> TrustedSource:
    row = (
        (
            await conn.execute(
                text(
                    f"""
                    UPDATE trusted_sources
                    SET status = 'revoked', revoked_at = now(), revoked_reason = :reason
                    WHERE host = :host
                    RETURNING {_COLUMNS}
                    """
                ),
                {"host": host, "reason": reason},
            )
        )
        .mappings()
        .one()
    )
    return _row_to_source(row)


async def get_trusted_source(conn: AsyncConnection, host: str) -> TrustedSource | None:
    """Returns the source only if its status is `trusted` -- a
    `pending_scan` or `revoked` row is indistinguishable from "not
    registered" to a caller, by design (FR-ADM-01-style deny-by-default:
    absence of an explicit `trusted` grant is always a deny)."""
    row = (
        (
            await conn.execute(
                text(f"SELECT {_COLUMNS} FROM trusted_sources WHERE host = :host AND status = 'trusted'"),
                {"host": host},
            )
        )
        .mappings()
        .first()
    )
    return _row_to_source(row) if row is not None else None
