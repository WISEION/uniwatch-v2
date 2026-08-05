"""FR-PLT-01, P117, NFR-OBS-01."""

from __future__ import annotations

import logging
import traceback

import httpx
import pytest
from fastapi import FastAPI

from packages.platform.correlation import CORRELATION_ID_HEADER, CorrelationIdMiddleware
from packages.platform.errors import ApiError, install_error_handlers


def make_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)
    install_error_handlers(app)

    @app.get("/boom/api-error")
    async def boom_api_error():
        raise ApiError(status_code=409, code="conflict", message="version mismatch")

    @app.get("/boom/unexpected")
    async def boom_unexpected():
        raise ValueError("something broke")

    @app.post("/echo")
    async def echo(payload: dict):
        return payload

    return app


@pytest.fixture
def client():
    app = make_app()
    # raise_app_exceptions=False: Starlette's ServerErrorMiddleware sends the
    # error response *and* re-raises for server-side logging (by design) —
    # without this the test transport would propagate that re-raise instead
    # of returning the response that was actually sent to the client.
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    return httpx.AsyncClient(transport=transport, base_url="http://test")


async def test_correlation_id_is_generated_when_absent(client):
    async with client:
        response = await client.get("/boom/unexpected")
    assert CORRELATION_ID_HEADER in response.headers
    assert len(response.headers[CORRELATION_ID_HEADER]) > 0


async def test_correlation_id_is_echoed_when_provided(client):
    async with client:
        response = await client.get("/boom/unexpected", headers={CORRELATION_ID_HEADER: "req-123"})
    assert response.headers[CORRELATION_ID_HEADER] == "req-123"
    assert response.json()["error"]["correlation_id"] == "req-123"


async def test_api_error_uses_declared_status_and_envelope_shape(client):
    async with client:
        response = await client.get("/boom/api-error", headers={CORRELATION_ID_HEADER: "req-abc"})
    assert response.status_code == 409
    body = response.json()
    assert body == {
        "error": {
            "code": "conflict",
            "message": "version mismatch",
            "correlation_id": "req-abc",
            "details": None,
        }
    }


async def test_unexpected_exception_is_500_with_envelope_not_traceback(client):
    async with client:
        response = await client.get("/boom/unexpected", headers={CORRELATION_ID_HEADER: "req-xyz"})
    assert response.status_code == 500
    body = response.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["correlation_id"] == "req-xyz"


async def test_unexpected_exception_is_logged_with_its_traceback(client, caplog):
    """The client is deliberately told nothing but `internal_error`, so the
    log is the only record of the real cause — it must exist and carry the
    stack (NFR-OBS-01)."""
    with caplog.at_level(logging.ERROR, logger="uniwatch.api.errors"):
        async with client:
            await client.get("/boom/unexpected")
    records = [r for r in caplog.records if r.name == "uniwatch.api.errors"]
    assert len(records) == 1
    assert records[0].exc_info is not None
    assert "something broke" in "".join(traceback.format_exception(*records[0].exc_info))


async def test_invalid_request_body_returns_422_with_field_details(client):
    async with client:
        response = await client.post("/echo", content=b"not-json", headers={"content-type": "application/json"})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "validation_error"
    assert isinstance(body["error"]["details"], list)
    assert len(body["error"]["details"]) >= 1
