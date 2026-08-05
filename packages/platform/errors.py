"""Unified error envelope with correlation id (FR-PLT-01, P117)."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from .correlation import CORRELATION_ID_HEADER, get_correlation_id_or_none

logger = logging.getLogger("uniwatch.api.errors")


class ErrorDetail(BaseModel):
    code: str
    message: str
    correlation_id: str | None
    details: list[dict] | None = None


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


class ApiError(Exception):
    """Raise from route/service code for any expected error condition —
    the handler below is the only place that turns it into an HTTP
    response, so the shape is uniform everywhere (FR-PLT-01)."""

    def __init__(
        self,
        status_code: int,
        code: str,
        message: str,
        details: list[dict] | None = None,
    ):
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message
        self.details = details


def _envelope_response(status_code: int, code: str, message: str, details=None) -> JSONResponse:
    correlation_id = get_correlation_id_or_none()
    body = ErrorEnvelope(
        error=ErrorDetail(
            code=code,
            message=message,
            correlation_id=correlation_id,
            details=details,
        )
    )
    # The bare-Exception handler is invoked by Starlette's ServerErrorMiddleware,
    # which sits *outside* CorrelationIdMiddleware and sends this response
    # directly — CorrelationIdMiddleware's header injection never runs for it.
    # Setting the header here directly keeps it present on every error path.
    headers = {CORRELATION_ID_HEADER: correlation_id} if correlation_id else None
    return JSONResponse(status_code=status_code, content=body.model_dump(), headers=headers)


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return _envelope_response(exc.status_code, exc.code, exc.message, exc.details)

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": [str(p) for p in e["loc"]], "msg": e["msg"], "type": e["type"]} for e in exc.errors()]
        return _envelope_response(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "validation_error",
            "request failed schema validation",
            details,
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        # The client deliberately gets a generic message with no traceback,
        # so this log is the only server-side record of what actually broke.
        # It carries the same correlation id the client was handed, which is
        # what makes a reported 500 traceable back to its stack (NFR-OBS-01).
        logger.exception("unhandled exception serving %s %s", request.method, request.url.path)
        return _envelope_response(
            status.HTTP_500_INTERNAL_SERVER_ERROR,
            "internal_error",
            "unexpected server error",
        )
