"""Correlation id: one value threaded through API request -> worker job ->
outbox row (NFR-OBS-01). `bind_correlation_id` is called once per HTTP
request (by `CorrelationIdMiddleware`) or once per worker job iteration (by
`apps/worker/main.py`, seeded from the job's own `correlation_id` column).
"""

from __future__ import annotations

import uuid
from contextvars import ContextVar

from starlette.datastructures import Headers, MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

CORRELATION_ID_HEADER = "X-Correlation-Id"

_correlation_id: ContextVar[str | None] = ContextVar("correlation_id", default=None)


def bind_correlation_id(value: str | None = None) -> str:
    value = value or str(uuid.uuid4())
    _correlation_id.set(value)
    return value


def get_correlation_id() -> str:
    value = _correlation_id.get()
    if value is None:
        raise RuntimeError("no correlation id bound in this context")
    return value


def get_correlation_id_or_none() -> str | None:
    return _correlation_id.get()


class CorrelationIdMiddleware:
    """Raw ASGI middleware (not `BaseHTTPMiddleware`) so exceptions raised by
    route handlers propagate to Starlette's `ServerErrorMiddleware`
    unmodified — `BaseHTTPMiddleware` is known to interfere with that in
    some Starlette versions."""

    def __init__(self, app: ASGIApp):
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        incoming = Headers(scope=scope).get(CORRELATION_ID_HEADER)
        correlation_id = bind_correlation_id(incoming)

        async def send_with_correlation_id(message: Message) -> None:
            if message["type"] == "http.response.start":
                MutableHeaders(scope=message).append(CORRELATION_ID_HEADER, correlation_id)
            await send(message)

        await self.app(scope, receive, send_with_correlation_id)
