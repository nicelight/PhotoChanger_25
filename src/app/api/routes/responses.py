"""Utility responses shared across API router scaffolding."""

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


def login_invalid_credentials() -> JSONResponse:
    """Return an ErrorResponse payload for invalid login attempts."""

    return JSONResponse(
        status_code=status.HTTP_401_UNAUTHORIZED,
        content={
            "error": {
                "code": "unauthorized",
                "message": "Неверный логин или пароль",
            }
        },
    )


def login_throttled() -> JSONResponse:
    """Return an ErrorResponse payload for throttled login attempts."""

    return JSONResponse(
        status_code=status.HTTP_429_TOO_MANY_REQUESTS,
        content={
            "error": {
                "code": "too_many_requests",
                "message": "Превышено количество попыток входа. Попробуйте позже.",
            }
        },
    )
