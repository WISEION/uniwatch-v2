"""Opaque cursor pagination (FR-PLT-05, P119). No offset anywhere — a cursor
encodes the last-seen sort key tuple, not a row count."""

from __future__ import annotations

import base64
import json


def encode_cursor(sort_key: tuple) -> str:
    raw = json.dumps(list(sort_key), separators=(",", ":"))
    return base64.urlsafe_b64encode(raw.encode("utf-8")).decode("ascii")


def decode_cursor(cursor: str) -> tuple:
    raw = base64.urlsafe_b64decode(cursor.encode("ascii")).decode("utf-8")
    return tuple(json.loads(raw))
