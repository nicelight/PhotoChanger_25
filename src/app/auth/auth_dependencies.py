"""Common authentication dependencies for FastAPI routers."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from .auth_service import (
    AuthService,
    InsufficientScopeError,
    InvalidTokenError,
    TokenExpiredError,
)

security = HTTPBearer(auto_error=False)


def get_auth_service(request: Request) -> AuthService:
    try:
        return request.app.state.auth_service  # type: ignore[attr-defined]
    except AttributeError as exc:  # pragma: no cover - defensive path
        raise RuntimeError("AuthService is not configured") from exc


def require_admin_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(security),
    service: AuthService = Depends(get_auth_service),
) -> dict:
    if credentials is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "failure_reason": "missing_token"},
        )

    token = credentials.credentials
    try:
        return service.validate_token(token, required_scope="admin")
    except TokenExpiredError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "failure_reason": "token_expired"},
        ) from exc
    except InvalidTokenError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "failure_reason": "invalid_token"},
        ) from exc
    except InsufficientScopeError as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={"status": "error", "failure_reason": "insufficient_scope"},
        ) from exc


__all__ = ["get_auth_service", "require_admin_user"]
