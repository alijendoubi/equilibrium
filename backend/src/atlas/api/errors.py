"""Stable, client-safe error envelopes for the public API."""

from typing import Any

from fastapi import HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict


class ApiError(BaseModel):
    """A machine-readable API error with a safe message for people."""

    model_config = ConfigDict(frozen=True)

    code: str
    message: str


class ErrorResponse(BaseModel):
    """Envelope shared by validation, not-found, rate-limit, and server errors."""

    model_config = ConfigDict(frozen=True)

    error: ApiError


_CODES = {
    404: "not_found",
    422: "validation_error",
    429: "rate_limited",
    503: "snapshot_unavailable",
}


def _message(detail: Any, fallback: str) -> str:
    return detail if isinstance(detail, str) and detail else fallback


async def http_error_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    """Turn explicit route errors into the documented envelope."""
    body = ErrorResponse(
        error=ApiError(
            code=_CODES.get(exc.status_code, "http_error"),
            message=_message(exc.detail, "Request failed"),
        )
    )
    return JSONResponse(status_code=exc.status_code, content=body.model_dump(), headers=exc.headers)


async def validation_error_handler(_request: Request, _exc: RequestValidationError) -> JSONResponse:
    """Avoid exposing framework-specific validation details as the public contract."""
    body = ErrorResponse(
        error=ApiError(code="validation_error", message="Request validation failed")
    )
    return JSONResponse(status_code=422, content=body.model_dump())
