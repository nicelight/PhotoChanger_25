"""Authentication router stubs aligned with the OpenAPI contract."""

from __future__ import annotations

from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from ..schemas import LoginRequest, LoginResponse
from .responses import endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Auth"])


@router.post(
    "/login",
    response_model=LoginResponse,
    status_code=status.HTTP_200_OK,
)
async def login_user(payload: LoginRequest) -> JSONResponse:
    """Вход пользователя и выдача JWT."""

    return endpoint_not_implemented("loginUser")


__all__ = ["router", "login_user"]
