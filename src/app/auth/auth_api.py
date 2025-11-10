"""Authentication API endpoints."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel

from .auth_service import (
    InvalidCredentialsError,
    LoginThrottledError,
)
from .auth_dependencies import get_auth_service

router = APIRouter(prefix="/api", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class LoginResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    expires_in: int


def _client_ip(request: Request) -> str | None:
    if request.client:
        return request.client.host
    return None


@router.post("/login", response_model=LoginResponse)
def login(payload: LoginRequest, request: Request, service: AuthService = Depends(get_auth_service)) -> LoginResponse:
    try:
        token, expires_in = service.authenticate(
            username=payload.username,
            password=payload.password,
            client_ip=_client_ip(request),
        )
    except LoginThrottledError as exc:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"status": "error", "failure_reason": "throttled", "details": str(exc)},
        ) from exc
    except InvalidCredentialsError as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"status": "error", "failure_reason": "invalid_credentials"},
        ) from exc
    return LoginResponse(access_token=token, expires_in=expires_in)
