"""Admin settings endpoints backed by :class:`SettingsService`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Annotated, Mapping, Optional, cast

from fastapi import APIRouter, Depends, Request, status
from fastapi.responses import JSONResponse

from ...domain.models import (
    MediaCacheSettings as DomainMediaCacheSettings,
    Settings as DomainSettings,
    SettingsDslrPasswordStatus as DomainSettingsDslrPasswordStatus,
    SettingsIngestConfig as DomainSettingsIngestConfig,
    SettingsProviderKeyStatus as DomainSettingsProviderKeyStatus,
)
from ...services import ServiceRegistry, SettingsService
from ...services.settings import SettingsUpdate
from ..errors import ApiError
from ..schemas import (
    MediaCachePurgeRequest,
    MediaCachePurgeResponse,
    MediaCacheSettings,
    Settings,
    SettingsDslrPasswordStatus,
    SettingsIngestConfig,
    SettingsProviderKeyStatus,
    SettingsUpdateRequest,
)
from .dependencies import (
    AdminPrincipal,
    ensure_permissions,
    require_bearer_authentication,
)
from .responses import endpoint_not_implemented

router = APIRouter(prefix="/api", tags=["Settings"])


def _get_settings_service(request: Request) -> SettingsService:
    registry = getattr(request.app.state, "service_registry", None)
    if not isinstance(registry, ServiceRegistry):  # pragma: no cover - defensive
        raise RuntimeError("service registry is not configured")
    factory = registry.resolve_settings_service()
    service = factory(config=getattr(request.app.state, "config", None))
    if not isinstance(service, SettingsService):  # pragma: no cover - misconfig guard
        raise RuntimeError("resolved service is not of type SettingsService")
    return cast(SettingsService, service)


def _map_settings(settings: DomainSettings) -> Settings:
    return Settings(
        dslr_password=_map_dslr_password(settings.dslr_password),
        provider_keys=_map_provider_keys(settings.provider_keys),
        ingest=_map_ingest(settings.ingest),
        media_cache=_map_media_cache(settings.media_cache),
    )


def _map_dslr_password(status: DomainSettingsDslrPasswordStatus) -> SettingsDslrPasswordStatus:
    return SettingsDslrPasswordStatus(
        is_set=status.is_set,
        updated_at=status.updated_at,
        updated_by=status.updated_by,
    )


def _map_ingest(config: DomainSettingsIngestConfig) -> SettingsIngestConfig:
    return SettingsIngestConfig(
        sync_response_timeout_sec=config.sync_response_timeout_sec,
        ingest_ttl_sec=config.ingest_ttl_sec,
    )


def _map_media_cache(settings: DomainMediaCacheSettings) -> MediaCacheSettings:
    return MediaCacheSettings(
        processed_media_ttl_hours=settings.processed_media_ttl_hours,
        public_link_ttl_sec=settings.public_link_ttl_sec,
    )


def _map_provider_keys(
    provider_keys: Mapping[str, DomainSettingsProviderKeyStatus],
) -> dict[str, SettingsProviderKeyStatus]:
    mapped: dict[str, SettingsProviderKeyStatus] = {}
    for provider_id, provider_status in provider_keys.items():
        extra = dict(getattr(provider_status, "extra", {}))
        mapped[provider_id] = SettingsProviderKeyStatus(
            is_configured=provider_status.is_configured,
            updated_at=provider_status.updated_at,
            updated_by=provider_status.updated_by,
            **extra,
        )
    return mapped


@router.get(
    "/settings",
    response_model=Settings,
    status_code=status.HTTP_200_OK,
)
async def get_platform_settings(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
    settings_service: Annotated[SettingsService, Depends(_get_settings_service)],
) -> Settings:
    """Получить глобальные настройки платформы."""

    ensure_permissions(principal, "settings:read")
    settings = settings_service.get_settings()
    return _map_settings(settings)


@router.put(
    "/settings",
    response_model=Settings,
    status_code=status.HTTP_200_OK,
)
async def update_platform_settings(
    principal: Annotated[AdminPrincipal, Depends(require_bearer_authentication)],
    payload: SettingsUpdateRequest,
    settings_service: Annotated[SettingsService, Depends(_get_settings_service)],
) -> Settings:
    """Обновить глобальные настройки и секреты."""

    ensure_permissions(principal, "settings:write")
    if payload.provider_keys not in (None, {}):
        raise ApiError(
            status.HTTP_422_UNPROCESSABLE_ENTITY,
            "provider_keys_not_supported",
            "Updating provider keys is not supported yet.",
        )

    updated_settings: DomainSettings | None = None
    try:
        if payload.ingest is not None:
            update_payload = SettingsUpdate(
                sync_response_timeout_sec=payload.ingest.sync_response_timeout_sec,
            )
            updated_settings = settings_service.update_settings(
                update_payload,
                updated_by=principal.username,
            )

        if payload.dslr_password is not None:
            rotated_settings, _ = settings_service.rotate_ingest_password(
                rotated_at=datetime.now(timezone.utc),
                updated_by=principal.username,
                new_password=payload.dslr_password.value,
            )
            updated_settings = rotated_settings

    except PermissionError as exc:  # pragma: no cover - enforced by ensure_permissions
        raise ApiError(
            status.HTTP_403_FORBIDDEN,
            "forbidden",
            "settings:write scope required",
        ) from exc
    except ValueError as exc:
        raise ApiError(
            status.HTTP_400_BAD_REQUEST,
            "invalid_settings_payload",
            str(exc),
        ) from exc

    if updated_settings is None:
        updated_settings = settings_service.get_settings()

    return _map_settings(updated_settings)


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
