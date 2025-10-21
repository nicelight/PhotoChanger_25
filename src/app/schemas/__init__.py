"""Lightweight DTOs used by repository implementations."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Generic, Mapping, TypeVar
from uuid import UUID

__all__ = [
    "AdminSettingDTO",
    "AdminSettingPayload",
    "Pagination",
    "Page",
    "ProcessingAggregateDTO",
    "SettingsSearchQuery",
    "SlotDTO",
    "SlotPayload",
    "SlotSearchQuery",
    "SlotTemplateDTO",
    "SlotTemplatePayload",
    "StatsQuery",
]


@dataclass(slots=True)
class Pagination:
    """Common pagination metadata."""

    page: int = 1
    per_page: int = 50
    total: int = 0


T = TypeVar("T")


@dataclass(slots=True)
class Page(Generic[T]):
    """Container for paginated repository results."""

    items: list[T]
    pagination: Pagination


@dataclass(slots=True)
class AdminSettingPayload:
    """Input payload for admin setting mutations."""

    key: str
    value: Any | None
    value_type: str | None
    is_secret: bool = False
    updated_by: str | None = None


@dataclass(slots=True)
class AdminSettingDTO(AdminSettingPayload):
    """DTO returned by repositories when loading admin settings."""

    etag: str = ""
    created_at: datetime | None = None
    updated_at: datetime | None = None


@dataclass(slots=True)
class SettingsSearchQuery:
    """Query parameters for listing admin settings."""

    pagination: Pagination = field(default_factory=Pagination)
    include_secrets: bool = False
    search: str | None = None


@dataclass(slots=True)
class SlotTemplatePayload:
    """Input payload for slot template attachments."""

    slot_id: str
    setting_key: str
    path: str
    mime: str
    size_bytes: int
    checksum: str | None = None
    label: str | None = None
    uploaded_by: str | None = None
    template_id: UUID | None = None


@dataclass(slots=True)
class SlotTemplateDTO(SlotTemplatePayload):
    """DTO describing a persisted slot template binding."""

    template_id: UUID
    created_at: datetime


@dataclass(slots=True)
class SlotPayload:
    """Input payload for slot mutations."""

    id: str
    name: str
    provider_id: str
    operation_id: str
    settings_json: Mapping[str, Any]
    last_reset_at: datetime | None = None
    updated_by: str | None = None


@dataclass(slots=True)
class SlotDTO(SlotPayload):
    """DTO returned by the slot repository."""

    created_at: datetime
    updated_at: datetime
    etag: str
    archived_at: datetime | None = None
    templates: list[SlotTemplateDTO] = field(default_factory=list)


@dataclass(slots=True)
class SlotSearchQuery:
    """Query parameters for paginated slot search."""

    pagination: Pagination = field(default_factory=Pagination)
    provider_id: str | None = None
    operation_id: str | None = None
    include_archived: bool = False
    search: str | None = None


@dataclass(slots=True)
class ProcessingAggregateDTO:
    """DTO describing aggregated processing statistics."""

    id: UUID
    slot_id: str | None
    granularity: str
    period_start: datetime
    period_end: datetime
    counters: Mapping[str, int]
    created_at: datetime
    updated_at: datetime


@dataclass(slots=True)
class StatsQuery:
    """Parameters for paginating processing aggregates."""

    pagination: Pagination = field(default_factory=Pagination)
    slot_id: str | None = None
    granularity: str | None = None
    period_start: datetime | None = None
    period_end: datetime | None = None

