"""One validated JSON GET (docs/architecture/egress-validator-contract.md).

Every live source fetcher does the same three things around
`fetch_via_validator`: require HTTP 200, decode the body as JSON, and hand
back both the raw bytes (the evidence that gets snapshotted) and the
parsed payload. A non-200 is surfaced as `UnexpectedResponseStatus`, never
absorbed into an empty payload (INV-11)."""

from __future__ import annotations

import json
from typing import Any

from sqlalchemy.ext.asyncio import AsyncConnection

from .fetch import fetch_via_validator
from .validator import EgressValidator


class UnexpectedResponseStatus(Exception):
    pass


async def fetch_json(
    conn: AsyncConnection, validator: EgressValidator, url: str, *, source_label: str
) -> tuple[bytes, dict[str, Any]]:
    status, body, _headers = await fetch_via_validator(conn, validator, url)
    if status != 200:
        raise UnexpectedResponseStatus(f"{source_label} returned HTTP {status} for {url!r}")
    return body, json.loads(body)
