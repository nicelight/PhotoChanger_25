"""Domain models for PhotoChanger described by the SDD blueprints.

The module exposes lightweight dataclasses and typed dictionaries that mirror
entities from ``spec/docs/blueprints/domain-model.md``. Only structural fields
are defined here; no persistence or validation logic is implemented at this
phase. Time-to-live (TTL) contracts and status progressions are reflected via
explicit fields and enums to make downstream layers deterministic.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Mapping, MutableMapping, TypedDict
from uuid import UUID


class JobStatus(str, Enum):
    """Processing states used by the queue worker.

    ``pending`` is the initial state for newly ingested jobs. When a worker
    acquires a job from PostgreSQL (``SELECT … FOR UPDATE SKIP LOCKED``), the
    state transitions to ``processing``. Finalization is tracked with
    ``is_finalized``/``failure_reason`` fields as described in the SDD.
    """

    PENDING = "pending"
    PROCESSING = "processing"


class ProcessingStatus(str, Enum):
    """Lifecycle states captured in :class:`ProcessingLog` records."""

    RECEIVED = "received"
    DISPATCHED = "dispatched"
    PROVIDER_RESPONDED = "provider_responded"
    TIMEOUT = "timeout"
    FAILED = "failed"
    SUCCEEDED = "succeeded"


class JobFailureReason(str, Enum):
    """Enumerates canonical failure reasons for ingest jobs."""

    TIMEOUT = "timeout"
    CANCELLED = "cancelled"
    PROVIDER_ERROR = "provider_error"


class SlotRecentResultRequired(TypedDict):
    """Mandatory fields for UI gallery entries.

    They mirror the ``Result`` schema from ``spec/contracts`` and carry TTL
    metadata (`result_expires_at = finalized_at + 72h`) that the UI relies on to
    hide expired artefacts.
    """

    job_id: UUID
    thumbnail_url: str
    download_url: str
    completed_at: datetime
    result_expires_at: datetime
    mime: str


class SlotRecentResult(SlotRecentResultRequired, total=False):
    """Optional fields complementing :class:`SlotRecentResultRequired`."""

    size_bytes: int | None


@dataclass(slots=True)
class Slot:
    """Static ingest slot described in the SDD blueprints."""

    id: str
    name: str
    provider_id: str
    operation_id: str
    settings_json: Mapping[str, Any]
    last_reset_at: datetime | None = None
    created_at: datetime
    updated_at: datetime
    recent_results: list[SlotRecentResult] = field(default_factory=list)


@dataclass(slots=True)
class Job:
    """Queue entry representing a single ingest processing request."""

    id: UUID
    slot_id: str
    status: JobStatus
    is_finalized: bool
    failure_reason: JobFailureReason | None
    expires_at: datetime
    created_at: datetime
    updated_at: datetime
    finalized_at: datetime | None = None
    payload_path: str | None = None
    provider_job_reference: str | None = None
    result_file_path: str | None = None
    result_inline_base64: str | None = None
    result_mime_type: str | None = None
    result_size_bytes: int | None = None
    result_checksum: str | None = None
    result_expires_at: datetime | None = None


@dataclass(slots=True)
class MediaObject:
    """Represents a temporary public link with a strict TTL.

    ``expires_at`` follows ``min(job.expires_at, created_at + T_public_link_ttl)``
    where ``T_public_link_ttl = T_sync_response``.
    """

    id: UUID
    job_id: UUID | None = None
    path: str
    public_url: str
    mime: str | None = None
    size_bytes: int | None = None
    expires_at: datetime
    created_at: datetime


@dataclass(slots=True)
class TemplateMedia:
    """Persistent template asset referenced by slots.

    ``slot_id``/``setting_key`` mirror the binding metadata exposed through the
    Template Media contracts in ``spec/contracts``.
    """

    id: UUID
    slot_id: str
    setting_key: str
    path: str
    mime: str
    size_bytes: int
    checksum: str | None = None
    label: str | None = None
    uploaded_by: str | None = None
    created_at: datetime


@dataclass(slots=True)
class ProcessingLog:
    """Audit trail describing worker/provider interactions."""

    id: UUID
    job_id: UUID
    slot_id: str
    status: ProcessingStatus
    message: str | None = None
    details: MutableMapping[str, Any] | None = None
    occurred_at: datetime
    provider_latency_ms: int | None = None


@dataclass(slots=True)
class SettingsDslrPasswordStatus:
    """Tracks whether the DSLR ingest password is configured."""

    is_set: bool
    updated_at: datetime | None
    updated_by: str | None


@dataclass(slots=True)
class SettingsProviderKeyStatus:
    """Stores provisioning status for an external provider.

    ``extra`` holds non-secret provider configuration parameters (for example,
    ``project_id``) as allowed by ``SettingsProviderKeyStatus`` contracts.
    """

    is_configured: bool
    updated_at: datetime | None
    updated_by: str | None
    extra: Mapping[str, str | int | float | bool] = field(default_factory=dict)


@dataclass(slots=True)
class SettingsIngestConfig:
    """Holds ingest deadlines derived from ``T_sync_response``."""

    sync_response_timeout_sec: int
    ingest_ttl_sec: int


@dataclass(slots=True)
class MediaCacheSettings:
    """Fixed TTL configuration for media cache maintenance.

    ``processed_media_ttl_hours`` is fixed at 72h per the SDD, while
    ``public_link_ttl_sec`` mirrors ``T_sync_response``.
    """

    processed_media_ttl_hours: int
    public_link_ttl_sec: int


@dataclass(slots=True)
class Settings:
    """Application-wide configuration, including TTL definitions."""

    dslr_password: SettingsDslrPasswordStatus
    provider_keys: Mapping[str, SettingsProviderKeyStatus] = field(
        default_factory=dict
    )
    ingest: SettingsIngestConfig
    media_cache: MediaCacheSettings


__all__ = [
    "Job",
    "JobFailureReason",
    "JobStatus",
    "MediaCacheSettings",
    "MediaObject",
    "ProcessingLog",
    "ProcessingStatus",
    "Settings",
    "SettingsDslrPasswordStatus",
    "SettingsIngestConfig",
    "SettingsProviderKeyStatus",
    "Slot",
    "SlotRecentResult",
    "TemplateMedia",
]
