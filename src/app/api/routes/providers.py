"""Provider catalogue router stubs."""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from ..schemas import ProviderListResponse
from .dependencies import require_bearer_authentication
from .responses import authentication_not_configured, endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Providers"])


@router.get(
    "/providers",
    response_model=ProviderListResponse,
    status_code=status.HTTP_200_OK,
)
async def list_providers(
    authenticated: Annotated[bool, Depends(require_bearer_authentication)],
) -> JSONResponse:
    """Получить короткий справочник провайдеров."""

    if not authenticated:
        return authentication_not_configured()
    return endpoint_not_implemented("listProviders")


__all__ = ["router", "list_providers"]
