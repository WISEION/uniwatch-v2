"""FR-PLT-04, FR-PLT-05, P115, P119."""

from __future__ import annotations

import pytest

from packages.platform.concurrency import PreconditionFailed, check_precondition
from packages.platform.idempotency import fingerprint
from packages.platform.pagination import InvalidCursor, decode_cursor, encode_cursor


def test_cursor_roundtrips_sort_key():
    cursor = encode_cursor((1723000000, 42))
    assert decode_cursor(cursor) == (1723000000, 42)


def test_cursor_is_opaque_not_a_raw_offset():
    cursor = encode_cursor((1, "abc"))
    assert cursor.isdigit() is False
    assert "1" not in cursor.split("=")[0][:1]  # not literally the offset "1" up front


def test_matching_version_passes_precondition():
    check_precondition("3", current_version=3)
    check_precondition('"3"', current_version=3)


def test_mismatched_version_raises_409_with_current_version():
    with pytest.raises(PreconditionFailed) as exc_info:
        check_precondition("2", current_version=3)
    assert exc_info.value.status_code == 409
    assert exc_info.value.details == [{"current_version": 3}]


def test_non_numeric_if_match_raises_precondition_failed():
    with pytest.raises(PreconditionFailed):
        check_precondition("not-a-version", current_version=1)


def test_fingerprint_changes_when_deadline_changes():
    base = {"title": "tender A", "deadline": "2026-09-01"}
    changed_deadline = {"title": "tender A", "deadline": "2026-09-15"}
    assert fingerprint(base) != fingerprint(changed_deadline)


def test_fingerprint_is_stable_for_same_payload_regardless_of_key_order():
    a = {"title": "x", "deadline": "2026-09-01"}
    b = {"deadline": "2026-09-01", "title": "x"}
    assert fingerprint(a) == fingerprint(b)


@pytest.mark.parametrize(
    "cursor",
    [
        "not-base64!!",
        "",
        encode_cursor(()),
        "eyJhIjogMX0=",  # base64 of a JSON object, not a list
        "gA==",  # valid base64, invalid UTF-8
        "W3RydWVd",  # base64 of [true] -- a bool is not a sort key value
    ],
)
def test_malformed_cursor_is_a_400_not_a_500(cursor):
    with pytest.raises(InvalidCursor) as exc:
        decode_cursor(cursor)
    assert exc.value.status_code == 400
    assert exc.value.code == "invalid_cursor"
