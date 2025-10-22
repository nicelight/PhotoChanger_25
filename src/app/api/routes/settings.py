"""Settings management router stubs for administrative operations.

Contracts align with ``spec/contracts/openapi.yaml`` to expose TTL configuration
and provider credential management without executing business logic yet.
"""

from __future__ import annotations

from typing import Annotated, Optional

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse

from ..schemas import (
    MediaCachePurgeRequest,
    MediaCachePurgeResponse,
    Settings,
    SettingsUpdateRequest,
)
from .dependencies import (
    AdminPrincipal,
    ensure_permissions,
    require_bearer_authentication,
)
from .responses import endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Settings"])


@router.get(
    "/settings",
    response_model=Settings,
    status_code=status.HTTP_200_OK,
)
async def get_platform_settings(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
) -> JSONResponse:
    """Получить глобальные настройки платформы."""

    ensure_permissions(principal, "settings:read")
    return endpoint_not_implemented("getPlatformSettings")


@router.put(
    "/settings",
    response_model=Settings,
    status_code=status.HTTP_200_OK,
)
async def update_platform_settings(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
    payload: SettingsUpdateRequest,
) -> JSONResponse:
    """Обновить глобальные настройки и секреты."""

    _ = payload
    ensure_permissions(principal, "settings:write")
    return endpoint_not_implemented("updatePlatformSettings")


@router.post(
    "/media/cache/purge",
    response_model=MediaCachePurgeResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
async def enqueue_media_cache_purge(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
    payload: Optional[MediaCachePurgeRequest] = None,
) -> JSONResponse:
    """Поставить задачу очистки медиа-кеша."""

    _ = payload
    ensure_permissions(principal, "settings:write")
    return endpoint_not_implemented("enqueueMediaCachePurge")


__all__ = [
    "router",
    "get_platform_settings",
    "update_platform_settings",
    "enqueue_media_cache_purge",
]
