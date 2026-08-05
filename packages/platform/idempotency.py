"""Idempotency key store for mutating routes (FR-PLT-03, P111).

The key alone does not disambiguate requests — two different requests could
accidentally reuse the same client-supplied key. `request_fingerprint` must
be derived by the caller from every attribute that makes the request
distinct (including e.g. a new deadline), so that a genuinely different
request reusing a key is rejected rather than silently treated as a replay.
"""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncConnection


def fingerprint(payload: dict) -> str:
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@dataclass(frozen=True)
class IdempotencyRecord:
    response_status: int
    response_body: dict


class IdempotencyReservationMissing(Exception):
    def __init__(self, key: str, route: str):
        super().__init__(f"no reservation row to store a response against for key {key!r} on {route!r}")
        self.key = key
        self.route = route


class IdempotencyKeyReused(Exception):
    def __init__(self, key: str, route: str):
        super().__init__(f"idempotency key {key!r} reused on {route!r} for a materially different request")
        self.key = key
        self.route = route


class IdempotencyStore:
    async def reserve(
        self,
        conn: AsyncConnection,
        key: str,
        route: str,
        request_fingerprint: str,
    ) -> IdempotencyRecord | None:
        """`None` means this is a brand-new reservation: the caller must
        perform the mutation and then call `store_response`. A returned
        `IdempotencyRecord` (only ever with `response_status` set) means
        this is a replay — the caller must return the stored response
        as-is and must not repeat the side effect."""
        inserted = (
            await conn.execute(
                text(
                    """
                    INSERT INTO idempotency_keys (idempotency_key, route, request_fingerprint)
                    VALUES (:key, :route, :fingerprint)
                    ON CONFLICT (idempotency_key, route) DO NOTHING
                    RETURNING idempotency_key
                    """
                ),
                {"key": key, "route": route, "fingerprint": request_fingerprint},
            )
        ).first()
        if inserted is not None:
            return None

        existing = (
            (
                await conn.execute(
                    text(
                        """
                    SELECT request_fingerprint, response_status, response_body
                    FROM idempotency_keys
                    WHERE idempotency_key = :key AND route = :route
                    """
                    ),
                    {"key": key, "route": route},
                )
            )
            .mappings()
            .one()
        )

        if existing["request_fingerprint"] != request_fingerprint:
            raise IdempotencyKeyReused(key, route)

        if existing["response_status"] is None:
            # Reserved by a request still in flight (crashed before storing a
            # response, or a genuine concurrent duplicate) — treat as new so
            # the caller can retry the mutation; store_response uses UPDATE,
            # which is safe to run again.
            return None

        body = existing["response_body"]
        if isinstance(body, str):
            body = json.loads(body)
        return IdempotencyRecord(existing["response_status"], body)

    async def store_response(
        self,
        conn: AsyncConnection,
        key: str,
        route: str,
        status_code: int,
        body: dict,
    ) -> None:
        """Must match the reservation `reserve` just made in this same
        transaction. A zero-row UPDATE means it does not — that would leave
        the key with no stored response, so the next replay of the same
        request would repeat the side effect instead of returning this
        response (FR-PLT-03). It is raised, never counted as stored."""
        result = await conn.execute(
            text(
                """
                UPDATE idempotency_keys
                SET response_status = :status, response_body = CAST(:body AS jsonb)
                WHERE idempotency_key = :key AND route = :route
                """
            ),
            {
                "key": key,
                "route": route,
                "status": status_code,
                "body": json.dumps(body),
            },
        )
        if result.rowcount == 0:
            raise IdempotencyReservationMissing(key, route)
