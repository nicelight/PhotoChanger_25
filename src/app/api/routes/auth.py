"""Authentication router stubs defined by ``spec/contracts/openapi.yaml``."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Annotated

import jwt
from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from ...core.config import AppConfig
from ...security.service import (
    AuthenticationError,
    AuthenticationService,
    ThrottlingError,
)
from ..schemas import LoginRequest, LoginResponse
from .dependencies import get_app_config, get_authentication_service
from .responses import login_invalid_credentials, login_throttled

router = APIRouter(prefix="/api", tags=["Auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login_user(
    payload: LoginRequest,
    config: Annotated[AppConfig, Depends(get_app_config)],
    auth_service: Annotated[AuthenticationService, Depends(get_authentication_service)],
) -> JSONResponse:
    """Вход пользователя и выдача JWT."""

    # Попытки аутентификации кешируются только в памяти приложения и очищаются
    # при рестарте (см. риск компрометации в constraints-risks blueprint).
    try:
        admin = auth_service.authenticate(payload.username, payload.password)
    except ThrottlingError:
        return login_throttled()
    except AuthenticationError:
        return login_invalid_credentials()

    ttl = int(config.jwt_access_ttl_seconds)
    issued_at = datetime.now(timezone.utc)
    expires_at = issued_at + timedelta(seconds=ttl)
    claims = {
        "sub": admin.username,
        "permissions": list(admin.permissions),
        "iat": int(issued_at.timestamp()),
        "exp": int(expires_at.timestamp()),
    }
    token = jwt.encode(claims, config.jwt_secret, algorithm="HS256")
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={
            "access_token": token,
            "token_type": "bearer",
            "expires_in_sec": ttl,
        },
    )


__all__ = ["router", "login_user"]
