"""Pydantic models derived from ``spec/contracts/schemas`` JSON contracts."""

from __future__ import annotations

from datetime import date, datetime
from typing import Any, Dict, List, Literal, Optional, Union
from uuid import UUID

from pydantic import AnyHttpUrl, BaseModel, ConfigDict, Field

SlotIdentifier = Literal[
    "slot-001",
    "slot-002",
    "slot-003",
    "slot-004",
    "slot-005",
    "slot-006",
    "slot-007",
    "slot-008",
    "slot-009",
    "slot-010",
    "slot-011",
    "slot-012",
    "slot-013",
    "slot-014",
    "slot-015",
]
"""Допустимый идентификатор статического ingest-слота."""


class Pagination(BaseModel):
    """Параметры пагинации стандартных административных выборок."""

    model_config = ConfigDict(extra="forbid")

    page: int = Field(..., ge=1, description="Текущая страница выборки.")
    page_size: int = Field(..., ge=1, description="Количество элементов на странице.")
    total: int = Field(..., ge=0, description="Общее количество элементов.")


class JobListPagination(Pagination):
    """Пагинация списка задач с ограничением размера страницы."""

    page_size: int = Field(
        ..., ge=1, le=100, description="Количество элементов на странице (максимум 100)."
    )


class GlobalStatsPagination(Pagination):
    """Пагинация глобальной статистики (ограничение параметров запроса)."""

    page_size: int = Field(
        ..., ge=1, le=50, description="Количество агрегатов на странице (максимум 50)."
    )


class AuthToken(BaseModel):
    """JWT токен доступа, выдаваемый после успешной аутентификации."""

    model_config = ConfigDict(extra="forbid")

    access_token: str = Field(..., description="JWT токен доступа")
    token_type: Literal["bearer"] = Field(..., description="Тип токена")
    expires_in_sec: int = Field(..., ge=1, description="Время жизни токена в секундах")


class LoginRequest(BaseModel):
    """Данные для входа предустановленного пользователя."""

    model_config = ConfigDict(extra="forbid")

    username: str = Field(..., min_length=1, description="Имя предустановленного пользователя")
    password: str = Field(..., min_length=1, description="Пароль пользователя")


class LoginResponse(AuthToken):
    """Ответ авторизации, совпадает со структурой ``AuthToken``."""


class ProviderSummary(BaseModel):
    """Короткая карточка AI-провайдера."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Машиночитаемый идентификатор провайдера")
    name: str = Field(..., description="Отображаемое имя провайдера")


class ProviderOperation(BaseModel):
    """Описание операции провайдера и требуемых полей."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Идентификатор операции")
    name: str = Field(..., description="Отображаемое имя операции")
    needs: List[str] = Field(
        ..., description="UI требования к полям (например, prompt, reference_image)"
    )
    schema_ref: str = Field(..., description="Путь к JSON Schema параметров операции")


class ProviderConfig(BaseModel):
    """Полная конфигурация AI-провайдера с операциями."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., description="Идентификатор провайдера")
    name: str = Field(..., description="Отображаемое имя провайдера")
    requires_public_media: bool = Field(
        ..., description="Нужно ли публичное медиа-хранилище для операций"
    )
    operations: List[ProviderOperation] = Field(..., description="Список поддерживаемых операций")


class ProviderListResponse(BaseModel):
    """Ответ справочника провайдеров."""

    model_config = ConfigDict(extra="forbid")

    providers: List[ProviderSummary] = Field(..., description="Коллекция провайдеров")


class ErrorPayload(BaseModel):
    """Детали ошибки REST API."""

    model_config = ConfigDict(extra="forbid")

    code: str = Field(..., description="Машиночитаемый код ошибки в snake_case")
    message: str = Field(..., description="Человекочитаемое описание проблемы")
    details: Optional[Dict[str, Any]] = Field(
        default=None, description="Дополнительные детали ошибки"
    )


class ErrorResponse(BaseModel):
    """Унифицированная обёртка ошибки API."""

    model_config = ConfigDict(extra="forbid")

    error: ErrorPayload


class Result(BaseModel):
    """Метаданные итогового файла обработки."""

    model_config = ConfigDict(extra="forbid")

    job_id: UUID = Field(..., description="Идентификатор Job, по которому получен результат")
    thumbnail_url: AnyHttpUrl = Field(..., description="URL превью изображения для галереи UI")
    download_url: AnyHttpUrl = Field(..., description="Публичная ссылка на итоговый файл")
    completed_at: datetime = Field(..., description="Метка времени финализации задачи")
    result_expires_at: datetime = Field(
        ..., description="Момент истечения TTL итогового файла (72 часа по умолчанию)"
    )
    mime: str = Field(..., pattern="^image/", description="MIME-тип итогового изображения")
    size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Размер итогового файла в байтах, если доступен",
    )


class Slot(BaseModel):
    """Статический ingest-слот и последние успешные результаты."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern="^slot-[0-9]{3}$", description="Идентификатор статического ingest-слота")
    name: str = Field(..., description="Отображаемое имя слота")
    provider_id: str = Field(..., description="Идентификатор провайдера")
    operation_id: str = Field(..., description="Идентификатор операции провайдера")
    settings_json: Dict[str, Any] = Field(
        ..., description="Параметры, сериализованные для провайдера"
    )
    last_reset_at: Optional[datetime] = Field(
        default=None, description="Метка последнего сброса статистики"
    )
    created_at: datetime = Field(..., description="Момент создания слота")
    updated_at: datetime = Field(..., description="Момент последнего обновления настроек")
    recent_results: List[Result] = Field(
        default_factory=list,
        description=(
            "Последние успешные результаты этого слота (не более 10 элементов, сортировка по"
            " completed_at убыванию)."
        ),
    )


class SlotListMeta(BaseModel):
    """Метаданные ответа списка слотов."""

    model_config = ConfigDict(extra="forbid")

    total: int = Field(..., ge=0, description="Количество доступных слотов")


class SlotListResponse(BaseModel):
    """Коллекция статических ingest-слотов."""

    model_config = ConfigDict(extra="forbid")

    data: List[Slot] = Field(..., description="Список слотов")
    meta: SlotListMeta


class SlotUpdateRequest(BaseModel):
    """Запрос обновления настроек слота."""

    model_config = ConfigDict(extra="forbid")

    name: str = Field(..., min_length=1, description="Новое имя слота")
    provider_id: str = Field(..., min_length=1, description="Идентификатор провайдера")
    operation_id: str = Field(..., min_length=1, description="Идентификатор операции провайдера")
    settings_json: Dict[str, Any] = Field(..., description="Конфигурация операции")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Текущая версия слота, полученная из последнего чтения",
    )


class SlotUpdateResponse(BaseModel):
    """Ответ обновления слота с новой меткой времени."""

    model_config = ConfigDict(extra="forbid")

    id: str = Field(..., pattern="^slot-[0-9]{3}$", description="Идентификатор слота")
    updated_at: datetime = Field(..., description="Момент последнего обновления")


class SlotStatsMetric(BaseModel):
    """Агрегированная метрика статистики по слоту."""

    model_config = ConfigDict(extra="forbid")

    period_start: Union[datetime, date] = Field(
        ..., description="Начало агрегируемого интервала"
    )
    period_end: Union[datetime, date] = Field(
        ..., description="Конец агрегируемого интервала"
    )
    success: int = Field(..., ge=0)
    timeouts: int = Field(..., ge=0)
    provider_errors: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    ingest_count: int = Field(..., ge=0)


class SlotStatsRange(BaseModel):
    """Диапазон агрегирования статистики слота."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    from_: Union[datetime, date] = Field(
        ..., alias="from", description="Начало выбранного диапазона статистики"
    )
    to: Union[datetime, date] = Field(
        ..., alias="to", description="Конец выбранного диапазона статистики"
    )
    group_by: Literal["hour", "day", "week"] = Field(
        ..., description="Гранулярность агрегирования метрик"
    )


class SlotStatsSummary(BaseModel):
    """Сводные показатели выбранного слота."""

    model_config = ConfigDict(extra="forbid")

    title: Optional[str] = Field(default=None, description="Подпись для UI")
    success: int = Field(..., ge=0)
    timeouts: int = Field(..., ge=0)
    provider_errors: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    ingest_count: int = Field(..., ge=0)
    last_reset_at: Optional[datetime] = Field(
        default=None, description="Момент последнего сброса статистики"
    )


class SlotStatsResponse(BaseModel):
    """Ответ статистики для конкретного слота."""

    model_config = ConfigDict(extra="forbid")

    slot_id: SlotIdentifier = Field(
        ..., description="Идентификатор слота, для которого рассчитана статистика"
    )
    range: SlotStatsRange
    summary: SlotStatsSummary
    metrics: List[SlotStatsMetric]


class GlobalStatsMetric(BaseModel):
    """Агрегированная метрика по всем слотам."""

    model_config = ConfigDict(extra="forbid")

    period_start: date = Field(..., description="Начало агрегируемого периода")
    period_end: date = Field(..., description="Конец агрегируемого периода")
    success: int = Field(..., ge=0)
    timeouts: int = Field(..., ge=0)
    provider_errors: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    ingest_count: int = Field(..., ge=0)


class GlobalStatsSummary(BaseModel):
    """Сводка глобальных показателей платформы."""

    model_config = ConfigDict(extra="forbid")

    total_runs: int = Field(..., ge=0)
    timeouts: int = Field(..., ge=0)
    provider_errors: int = Field(..., ge=0)
    cancelled: int = Field(..., ge=0)
    errors: int = Field(..., ge=0)
    ingest_count: int = Field(..., ge=0)


class GlobalStatsResponse(BaseModel):
    """Ответ агрегированной статистики по слотам."""

    model_config = ConfigDict(extra="forbid")

    summary: GlobalStatsSummary
    data: List[GlobalStatsMetric]
    meta: GlobalStatsPagination


class MediaObject(BaseModel):
    """Публичная ссылка на временное медиа."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(..., description="Идентификатор временного медиа")
    public_url: AnyHttpUrl = Field(..., description="Публичный URL для скачивания")
    expires_at: datetime = Field(
        ..., description="Момент истечения ссылки (равен T_sync_response)"
    )
    mime: Optional[str] = Field(
        default=None, pattern="^image/", description="MIME-тип загруженного файла"
    )
    size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Размер файла в байтах",
    )
    job_id: Optional[UUID] = Field(
        default=None, description="Идентификатор Job, для которой зарегистрирован файл"
    )


class MediaRegisterRequest(BaseModel):
    """Запрос на регистрацию временного медиа-объекта."""

    model_config = ConfigDict(extra="forbid")

    file: bytes = Field(..., description="Изображение, загружаемое во временное хранилище")
    job_id: Optional[UUID] = Field(
        default=None, description="Идентификатор задачи обработки, к которой привязан файл"
    )


class TemplateMediaRegisterRequest(BaseModel):
    """Запрос загрузки шаблонного медиа для слота."""

    model_config = ConfigDict(extra="forbid")

    file: bytes = Field(..., description="Файл шаблона для постоянного хранения")
    slot_id: SlotIdentifier = Field(
        ..., description="Идентификатор слота, к которому привязывается шаблон"
    )
    setting_key: str = Field(
        ..., description="Ключ настройки в Slot.settings_json, который ссылается на шаблон"
    )
    label: Optional[str] = Field(
        default=None, description="Человекочитаемое название шаблона"
    )
    replace: Optional[bool] = Field(
        default=None, description="Флаг замены существующей привязки шаблона"
    )


class TemplateMediaObject(BaseModel):
    """Метаданные загруженного шаблонного медиа."""

    model_config = ConfigDict(extra="forbid")

    id: UUID = Field(..., description="Идентификатор шаблонного медиа")
    slot_id: SlotIdentifier = Field(..., description="Слот, с которым связана загрузка")
    setting_key: str = Field(..., description="Ключ настройки, к которому привязан шаблон")
    label: Optional[str] = Field(default=None, description="Необязательный ярлык шаблона")
    checksum: Optional[str] = Field(
        default=None,
        pattern="^[A-Fa-f0-9]{64}$",
        description="Контрольная сумма файла (например, SHA-256 в hex)",
    )
    mime: str = Field(..., description="MIME-тип сохранённого файла")
    size_bytes: int = Field(..., ge=0, description="Размер файла в байтах")
    uploaded_by: Optional[str] = Field(
        default=None, description="Администратор, загрузивший шаблон"
    )
    created_at: datetime = Field(..., description="Момент загрузки шаблона")


class MediaCacheSettings(BaseModel):
    """Настройки TTL медиа-хранилища."""

    model_config = ConfigDict(extra="forbid")

    processed_media_ttl_hours: Literal[72] = Field(
        ..., description="Фиксированный срок хранения итоговых Result в часах"
    )
    public_link_ttl_sec: int = Field(
        ..., ge=45, le=60, description="Срок жизни временных публичных ссылок в секундах"
    )


class MediaCachePurgeRequest(BaseModel):
    """Параметры планирования очистки медиа-кеша."""

    model_config = ConfigDict(extra="forbid")

    scope: Optional[Literal["full", "media_objects"]] = Field(
        default=None,
        description="Режим очистки: полная (Result + media_object) или только временные media_object",
    )


class MediaCachePurgeResponse(BaseModel):
    """Ответ постановки задачи очистки медиа-кеша."""

    model_config = ConfigDict(extra="forbid")

    status: Literal["queued_for_gc"] = Field(
        ..., description="Статус постановки задания очистки"
    )
    scope: Literal["full", "media_objects"] = Field(
        ..., description="Режим, с которым запланирована очистка"
    )
    job_id: str = Field(..., description="Идентификатор фонового задания очистки")
    expires_cutoff: datetime = Field(
        ..., description="Пороговый момент времени, до которого будут удалены устаревшие сущности"
    )


class SettingsDslrPasswordStatus(BaseModel):
    """Состояние DSLR-пароля платформы."""

    model_config = ConfigDict(extra="forbid")

    is_set: bool = Field(..., description="Признак того, что DSLR-пароль установлен")
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Момент последнего обновления значения либо null, если пароль не задавался",
    )
    updated_by: Optional[str] = Field(
        default=None, description="Логин пользователя, выполнившего обновление"
    )


class SettingsProviderKeyStatus(BaseModel):
    """Состояние секрета провайдера и дополнительных параметров."""

    model_config = ConfigDict(extra="allow")

    is_configured: bool = Field(
        ..., description="Показывает, что секреты и обязательные параметры для провайдера заданы"
    )
    updated_at: Optional[datetime] = Field(
        default=None,
        description="Момент последнего обновления секрета или null, если значение ещё не задавалось",
    )
    updated_by: Optional[str] = Field(
        default=None, description="Логин пользователя, обновившего секрет"
    )


class SettingsProviderKeyUpdate(BaseModel):
    """Запрос обновления секрета провайдера."""

    model_config = ConfigDict(extra="forbid")

    api_key: str = Field(..., min_length=1, description="Новый API-ключ провайдера")


class SettingsIngestConfig(BaseModel):
    """Настройки таймаутов ingest API."""

    model_config = ConfigDict(extra="forbid")

    sync_response_timeout_sec: int = Field(
        ..., ge=45, le=60, description="Таймаут синхронного ожидания ingest в секундах"
    )
    ingest_ttl_sec: int = Field(
        ..., ge=45, le=60, description="Вычисленный TTL исходных payload: T_sync_response"
    )


class Settings(BaseModel):
    """Глобальные настройки платформы и состояние секретов."""

    model_config = ConfigDict(extra="forbid")

    dslr_password: SettingsDslrPasswordStatus
    provider_keys: Dict[str, SettingsProviderKeyStatus] = Field(
        ..., description="Секреты и параметры провайдеров"
    )
    ingest: SettingsIngestConfig
    media_cache: MediaCacheSettings


class SettingsResponse(Settings):
    """Ответ администратора с текущими настройками."""


class DslrPasswordUpdate(BaseModel):
    """Значение для обновления DSLR-пароля."""

    model_config = ConfigDict(extra="forbid")

    value: str = Field(
        ..., min_length=1, description="Новый пароль, который будет захеширован"
    )


class SettingsIngestUpdate(BaseModel):
    """Запрос обновления таймаута ingest."""

    model_config = ConfigDict(extra="forbid")

    sync_response_timeout_sec: int = Field(
        ..., ge=45, le=60, description="Новое значение T_sync_response в секундах"
    )


class SettingsUpdateRequest(BaseModel):
    """Запрос на частичное обновление глобальных настроек."""

    model_config = ConfigDict(extra="forbid")

    dslr_password: Optional[DslrPasswordUpdate] = Field(
        default=None,
        description="Секция обновления DSLR-пароля. Передача значения перехеширует пароль",
    )
    provider_keys: Optional[Dict[str, SettingsProviderKeyUpdate]] = Field(
        default=None,
        description="Карточки провайдеров для обновления секретов и публичных параметров",
    )
    ingest: Optional[SettingsIngestUpdate] = Field(
        default=None,
        description="Настройка таймаута синхронного ожидания ingest и связанных TTL",
    )


class Job(BaseModel):
    """Базовая запись очереди задач обработки."""

    model_config = ConfigDict(extra="forbid")

    id: UUID
    slot_id: SlotIdentifier = Field(
        ..., description="Идентификатор слота, из которого была создана задача"
    )
    status: Literal["pending", "processing"] = Field(
        ..., description="Промежуточное состояние обработки до финализации"
    )
    is_finalized: bool = Field(..., description="Признак того, что задача завершена")
    failure_reason: Optional[Literal["timeout", "provider_error", "cancelled"]] = Field(
        default=None,
        description="Причина неуспешного завершения, если обработка не удалась",
    )
    provider_job_reference: Optional[str] = Field(
        default=None,
        description="Идентификатор очереди внешнего провайдера",
    )
    payload_path: Optional[str] = Field(
        default=None, description="Путь к исходному ingest-файлу во временном хранилище"
    )
    result_file_path: Optional[str] = Field(
        default=None,
        description="Относительный путь к итоговому файлу результата в MEDIA_ROOT/results",
    )
    result_inline_base64: Optional[str] = Field(
        default=None,
        description="Временная base64-строка результата для синхронного ответа ingest",
    )
    result_mime_type: Optional[str] = Field(
        default=None, description="MIME-тип итогового изображения"
    )
    result_size_bytes: Optional[int] = Field(
        default=None,
        ge=0,
        description="Размер результата в байтах",
    )
    result_checksum: Optional[str] = Field(
        default=None, description="Контрольная сумма содержимого"
    )
    result_expires_at: Optional[datetime] = Field(
        default=None,
        description="Момент автоочистки итогового файла",
    )
    expires_at: datetime = Field(
        ..., description="Единый дедлайн задачи: created_at + T_sync_response"
    )
    created_at: datetime
    updated_at: datetime
    finalized_at: Optional[datetime] = Field(
        default=None, description="Момент фиксации финального состояния"
    )


class JobDeadline(BaseModel):
    """Единый дедлайн и остаток времени задачи."""

    model_config = ConfigDict(extra="forbid")

    expires_at: datetime = Field(
        ..., description="Момент, когда задача обязана быть финализирована"
    )
    remaining_ms: int = Field(
        ..., description="Оставшееся время до дедлайна в миллисекундах"
    )


DeadlineInfo = JobDeadline
"""Алиас для подчёркивания повторного использования дедлайна."""


class JobMetrics(BaseModel):
    """Сводные тайминги ожидания и обработки."""

    model_config = ConfigDict(extra="forbid")

    queue_wait_ms: Optional[int] = Field(
        default=None, ge=0, description="Сколько миллисекунд задача провела в очереди"
    )
    processing_ms: Optional[int] = Field(
        default=None, ge=0, description="Продолжительность обработки воркером"
    )
    total_elapsed_ms: Optional[int] = Field(
        default=None,
        ge=0,
        description="Общее время от постановки в очередь до текущего момента или финализации",
    )


class JobAdminView(BaseModel):
    """Агрегированное представление задачи для административного мониторинга."""

    model_config = ConfigDict(extra="forbid")

    job: Job = Field(..., description="Базовая запись очереди")
    deadline: JobDeadline = Field(
        ..., description="Единый дедлайн и остаток времени"
    )
    metrics: JobMetrics = Field(..., description="Сводные тайминги ожидания и обработки")


class JobListResponse(BaseModel):
    """Список задач ingest-очереди с пагинацией."""

    model_config = ConfigDict(extra="forbid")

    data: List[JobAdminView] = Field(
        ..., description="Список агрегированных представлений задач очереди"
    )
    meta: JobListPagination = Field(
        ..., description="Параметры пагинации списка задач"
    )


class JobDetailResponse(JobAdminView):
    """Подробная информация о задаче."""


class IngestRequest(BaseModel):
    """Multipart-запрос ingest от DSLR Remote Pro."""

    model_config = ConfigDict(extra="allow", populate_by_name=True)

    password: str = Field(..., min_length=1, description="Глобальный пароль ingest")
    file_to_upload: bytes = Field(
        ..., alias="fileToUpload", description="Основной файл изображения"
    )


__all__ = [
    "AuthToken",
    "LoginRequest",
    "LoginResponse",
    "ProviderSummary",
    "ProviderOperation",
    "ProviderConfig",
    "ProviderListResponse",
    "ErrorPayload",
    "ErrorResponse",
    "Result",
    "Slot",
    "SlotListMeta",
    "SlotListResponse",
    "SlotUpdateRequest",
    "SlotUpdateResponse",
    "SlotStatsMetric",
    "SlotStatsRange",
    "SlotStatsSummary",
    "SlotStatsResponse",
    "GlobalStatsMetric",
    "GlobalStatsSummary",
    "GlobalStatsResponse",
    "MediaObject",
    "MediaRegisterRequest",
    "TemplateMediaRegisterRequest",
    "TemplateMediaObject",
    "MediaCacheSettings",
    "MediaCachePurgeRequest",
    "MediaCachePurgeResponse",
    "SettingsDslrPasswordStatus",
    "SettingsProviderKeyStatus",
    "SettingsProviderKeyUpdate",
    "SettingsIngestConfig",
    "Settings",
    "SettingsResponse",
    "DslrPasswordUpdate",
    "SettingsIngestUpdate",
    "SettingsUpdateRequest",
    "Job",
    "JobDeadline",
    "DeadlineInfo",
    "JobMetrics",
    "JobAdminView",
    "JobListResponse",
    "JobDetailResponse",
    "IngestRequest",
    "Pagination",
    "JobListPagination",
    "GlobalStatsPagination",
    "SlotIdentifier",
]
