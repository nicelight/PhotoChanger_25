"""Utility helpers for stubbed HTTP responses."""

from __future__ import annotations

from fastapi import status
from fastapi.responses import JSONResponse


def authentication_not_configured() -> JSONResponse:
    """Return a uniform response for missing authentication wiring."""

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": "Bearer authentication is not wired yet."},
    )


def endpoint_not_implemented(operation: str) -> JSONResponse:
    """Return a standard 501 response for unimplemented handlers."""

    return JSONResponse(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        content={"detail": f"Endpoint '{operation}' is not implemented."},
    )
