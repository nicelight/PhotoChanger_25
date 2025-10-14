"""Typed HTTP client facade for PhotoChanger REST API."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Optional
from uuid import UUID

from httpx import AsyncClient

from .schemas import (
    IngestRequest,
    JobDetailResponse,
    JobListResponse,
    LoginRequest,
    LoginResponse,
    MediaCachePurgeRequest,
    MediaCachePurgeResponse,
    MediaObject,
    MediaRegisterRequest,
    ProviderListResponse,
    Settings,
    SettingsUpdateRequest,
    Slot,
    SlotIdentifier,
    SlotListResponse,
    SlotStatsResponse,
    SlotUpdateRequest,
    SlotUpdateResponse,
    TemplateMediaObject,
    TemplateMediaRegisterRequest,
    GlobalStatsResponse,
)


@dataclass(slots=True)
class ApiClient:
    """Convenience wrapper around :class:`httpx.AsyncClient` with typed responses."""

    http: AsyncClient

    async def login(self, payload: LoginRequest) -> LoginResponse:
        """Вход пользователя и выдача JWT."""

        raise NotImplementedError("API client login stub is not implemented.")

    async def list_providers(self) -> ProviderListResponse:
        """Получить короткий справочник провайдеров."""

        raise NotImplementedError(
            "API client provider listing stub is not implemented."
        )

    async def list_slots(
        self,
        provider_id: Optional[str] = None,
        operation_id: Optional[str] = None,
        search: Optional[str] = None,
    ) -> SlotListResponse:
        """Получить список статических ingest-слотов."""

        raise NotImplementedError("API client slot listing stub is not implemented.")

    async def get_slot(self, slot_id: SlotIdentifier) -> Slot:
        """Получить данные конкретного слота вместе с последними результатами."""

        raise NotImplementedError("API client slot retrieval stub is not implemented.")

    async def update_slot(
        self,
        slot_id: SlotIdentifier,
        payload: SlotUpdateRequest,
        if_match: Optional[str] = None,
    ) -> SlotUpdateResponse:
        """Обновить настройки слота с учётом проверки версии."""

        raise NotImplementedError("API client slot update stub is not implemented.")

    async def reset_slot_stats(self, slot_id: SlotIdentifier) -> None:
        """Сбросить статистику указанного слота."""

        raise NotImplementedError("API client slot reset stub is not implemented.")

    async def get_platform_settings(self) -> Settings:
        """Получить глобальные настройки платформы."""

        raise NotImplementedError(
            "API client settings retrieval stub is not implemented."
        )

    async def update_platform_settings(
        self, payload: SettingsUpdateRequest
    ) -> Settings:
        """Обновить глобальные настройки и секреты."""

        raise NotImplementedError("API client settings update stub is not implemented.")

    async def enqueue_media_cache_purge(
        self, payload: Optional[MediaCachePurgeRequest] = None
    ) -> MediaCachePurgeResponse:
        """Поставить задачу очистки медиа-кеша."""

        raise NotImplementedError(
            "API client media cache purge stub is not implemented."
        )

    async def list_jobs(
        self,
        status_filter: Optional[Literal["pending", "processing"]] = None,
        is_finalized: Optional[bool] = None,
        failure_reason: Optional[
            Literal["timeout", "provider_error", "cancelled"]
        ] = None,
        slot_id: Optional[SlotIdentifier] = None,
        page: int = 1,
        page_size: int = 20,
        sort_by: Literal["created_at", "expires_at"] = "expires_at",
        sort_order: Literal["asc", "desc"] = "asc",
    ) -> JobListResponse:
        """Получить список задач ingest-очереди."""

        raise NotImplementedError("API client job listing stub is not implemented.")

    async def get_job(self, job_id: UUID) -> JobDetailResponse:
        """Получить подробную информацию о задаче."""

        raise NotImplementedError("API client job retrieval stub is not implemented.")

    async def register_media(self, payload: MediaRegisterRequest) -> MediaObject:
        """Зарегистрировать временное медиа и получить публичную ссылку."""

        raise NotImplementedError(
            "API client media registration stub is not implemented."
        )

    async def register_template_media(
        self, payload: TemplateMediaRegisterRequest
    ) -> TemplateMediaObject:
        """Загрузить шаблон и привязать его к слоту."""

        raise NotImplementedError(
            "API client template media registration stub is not implemented."
        )

    async def delete_template_media(
        self,
        media_id: UUID,
        slot_id: SlotIdentifier,
        setting_key: str,
        force: Optional[bool] = None,
    ) -> None:
        """Удалить шаблонное медиа и отвязать от слота."""

        raise NotImplementedError(
            "API client template media deletion stub is not implemented."
        )

    async def get_public_media(self, media_id: UUID) -> bytes:
        """Получить временный файл по публичной ссылке."""

        raise NotImplementedError(
            "API client public media download stub is not implemented."
        )

    async def download_public_result(self, job_id: UUID) -> bytes:
        """Скачать итоговый файл обработки."""

        raise NotImplementedError(
            "API client public result download stub is not implemented."
        )

    async def get_slot_stats(
        self,
        slot_id: SlotIdentifier,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        group_by: Literal["hour", "day", "week"] = "day",
    ) -> SlotStatsResponse:
        """Получить статистику по слоту."""

        raise NotImplementedError("API client slot stats stub is not implemented.")

    async def get_global_stats(
        self,
        from_dt: Optional[datetime] = None,
        to_dt: Optional[datetime] = None,
        group_by: Literal["day", "week", "month"] = "week",
        page: int = 1,
        page_size: int = 10,
        sort_by: Literal[
            "period_start", "success", "errors", "ingest_count"
        ] = "period_start",
        sort_order: Literal["asc", "desc"] = "desc",
        provider_id: Optional[str] = None,
        slot_id: Optional[SlotIdentifier] = None,
    ) -> GlobalStatsResponse:
        """Получить агрегированную статистику по слотам."""

        raise NotImplementedError("API client global stats stub is not implemented.")

    async def ingest_slot(
        self, slot_id: SlotIdentifier, payload: IngestRequest
    ) -> bytes:
        """Принять ingest-запрос от DSLR Remote Pro."""

        raise NotImplementedError("API client ingest stub is not implemented.")


__all__ = ["ApiClient"]
