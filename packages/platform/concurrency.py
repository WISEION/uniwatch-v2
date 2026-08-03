"""Optimistic concurrency: ETag / version precondition (FR-PLT-04, P115, INV-12)."""

from __future__ import annotations

from .errors import ApiError


class PreconditionFailed(ApiError):
    def __init__(self, current_version: int):
        super().__init__(
            status_code=409,
            code="precondition_failed",
            message="resource was modified concurrently",
            details=[{"current_version": current_version}],
        )
        self.current_version = current_version


def check_precondition(if_match: str, current_version: int) -> None:
    """`if_match` is the client-supplied `If-Match` header value (an
    integer version, optionally quoted like a real ETag: `"3"` or `3`).
    Raises `PreconditionFailed` (409, current version included so the
    client can render a conflict diff) unless it matches `current_version`
    exactly."""
    try:
        expected_version = int(if_match.strip('"'))
    except ValueError as exc:
        raise PreconditionFailed(current_version) from exc
    if expected_version != current_version:
        raise PreconditionFailed(current_version)
