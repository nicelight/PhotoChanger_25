"""Reusable error primitives for API exception handling."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

from fastapi import Request, status
from fastapi.responses import JSONResponse


@dataclass(slots=True)
class ApiError(Exception):
    """Structured application-level error for HTTP handlers."""

    status_code: int
    code: str
    message: str
    headers: Mapping[str, str] | None = None

    def to_response(self) -> JSONResponse:
        """Materialise the error into a ``JSONResponse`` instance."""

        return JSONResponse(
            status_code=self.status_code,
            content={"error": {"code": self.code, "message": self.message}},
            headers=dict(self.headers or {}),
        )


async def api_error_handler(_: Request, exc: ApiError) -> JSONResponse:
    """Convert :class:`ApiError` exceptions into JSON payloads."""

    return exc.to_response()


def unauthorized_error(message: str) -> ApiError:
    """Return an :class:`ApiError` representing an authentication failure."""

    return ApiError(status.HTTP_401_UNAUTHORIZED, "unauthorized", message)


def forbidden_error(message: str) -> ApiError:
    """Return an :class:`ApiError` representing an authorisation failure."""

    return ApiError(status.HTTP_403_FORBIDDEN, "forbidden", message)


__all__ = ["ApiError", "api_error_handler", "forbidden_error", "unauthorized_error"]
