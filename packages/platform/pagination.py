"""Opaque cursor pagination (FR-PLT-05, P119). No offset anywhere — a cursor
encodes the last-seen sort key tuple, not a row count."""

from __future__ import annotations

import base64
import binascii
import json


class InvalidCursor(ValueError):
    """A cursor the server did not produce (truncated, hand-edited, or from
    another route's key shape). Typed so callers can answer the client with
    a 4xx for its own bad input instead of letting a raw decoding error
    surface as an internal server error (FR-PLT-01)."""

    def __init__(self, cursor: str):
        super().__init__(f"cursor is not a valid opaque cursor: {cursor!r}")
        self.cursor = cursor


def encode_cursor(sort_key: tuple) -> str:
    raw = json.dumps(list(sort_key), separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        decoded = json.loads(raw)
    except (binascii.Error, UnicodeError, json.JSONDecodeError) as exc:
        raise InvalidCursor(cursor) from exc
    if not isinstance(decoded, list):
        raise InvalidCursor(cursor)
    return tuple(decoded)
