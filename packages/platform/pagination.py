"""Opaque cursor pagination (FR-PLT-05, P119). No offset anywhere — a cursor
encodes the last-seen sort key tuple, not a row count."""

from __future__ import annotations

import base64
import binascii
import json

from .errors import ApiError


class InvalidCursor(ApiError):
    def __init__(self) -> None:
        super().__init__(status_code=400, code="invalid_cursor", message="cursor is not a valid pagination cursor")


def encode_cursor(sort_key: tuple) -> str:
    raw = json.dumps(list(sort_key), separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple:
    """A cursor is client-supplied, so every malformed shape (bad base64,
    bad UTF-8, non-JSON, a JSON value that is not a list of scalars, or an
    empty list) is a 400 `invalid_cursor` — never an unhandled exception
    surfacing as a 500."""
    try:
        raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
        decoded = json.loads(raw)
    except (UnicodeDecodeError, UnicodeEncodeError, binascii.Error, ValueError) as exc:
        raise InvalidCursor() from exc
    if not isinstance(decoded, list) or not decoded:
        raise InvalidCursor()
    if any(not isinstance(part, (int, str, float)) or isinstance(part, bool) for part in decoded):
        raise InvalidCursor()
    return tuple(decoded)
