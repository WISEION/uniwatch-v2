"""NFR-OBS-01: structured logs carry the correlation id bound to the current context."""

from __future__ import annotations

import json
import logging

from packages.platform.correlation import bind_correlation_id
from packages.platform.logging import JsonFormatter


def _make_record(message: str) -> logging.LogRecord:
    return logging.LogRecord(
        name="uniwatch.test",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=message,
        args=(),
        exc_info=None,
    )


def test_formatted_log_line_is_valid_json_with_message_and_level():
    record = _make_record("hello world")
    line = JsonFormatter().format(record)
    payload = json.loads(line)
    assert payload["message"] == "hello world"
    assert payload["level"] == "INFO"
    assert payload["logger"] == "uniwatch.test"


def test_formatted_log_line_carries_bound_correlation_id():
    bind_correlation_id("corr-42")
    record = _make_record("bound")
    payload = json.loads(JsonFormatter().format(record))
    assert payload["correlation_id"] == "corr-42"


def test_formatted_log_line_has_null_correlation_id_when_unbound():
    from packages.platform import correlation

    token = correlation._correlation_id.set(None)
    try:
        record = _make_record("unbound")
        payload = json.loads(JsonFormatter().format(record))
        assert payload["correlation_id"] is None
    finally:
        correlation._correlation_id.reset(token)
