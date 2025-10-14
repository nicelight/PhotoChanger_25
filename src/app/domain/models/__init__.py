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
    VALIDATION_ERROR = "validation_error"
    UNKNOWN = "unknown"


class SlotRecentResult(TypedDict, total=False):
    """Snapshot of the latest results returned by a slot UI page.

    The UI shows a gallery of recent jobs with their TTLs. The fields capture
    the ``finalized_at`` timestamp and the ``result_expires_at`` deadline to
    respect the 72h retention window from the domain model.
    """

    job_id: UUID
    result_file_path: str
    public_url: str
    finalized_at: datetime
    result_expires_at: datetime


@dataclass(slots=True)
class Slot:
    """Static ingest slot described in the SDD blueprints."""

    id: str
    name: str
    provider: str
    operation: str
    settings_json: Mapping[str, Any]
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
    finalized_at: datetime | None
    payload_path: str | None
    provider_job_reference: str | None
    result_file_path: str | None
    result_inline_base64: str | None
    result_mime_type: str | None
    result_size_bytes: int | None
    result_checksum: str | None
    result_expires_at: datetime | None


@dataclass(slots=True)
class MediaObject:
    """Represents a temporary public link with a strict TTL."""

    id: UUID
    job_id: UUID | None
    path: str
    mime: str
    size_bytes: int
    expires_at: datetime
    created_at: datetime


@dataclass(slots=True)
class TemplateMedia:
    """Persistent template asset referenced by slots."""

    id: UUID
    path: str
    mime: str
    size_bytes: int
    checksum: str
    label: str
    uploaded_by: str
    created_at: datetime


@dataclass(slots=True)
class ProcessingLog:
    """Audit trail describing worker/provider interactions."""

    id: UUID
    job_id: UUID
    slot_id: str
    status: ProcessingStatus
    message: str | None
    details: MutableMapping[str, Any] | None
    occurred_at: datetime
    provider_latency_ms: int | None


@dataclass(slots=True)
class Settings:
    """Application-wide configuration, including TTL definitions."""

    ingest_sync_response_timeout_sec: int
    media_public_link_ttl_sec: int
    media_ingest_ttl_sec: int
    media_result_retention_sec: int
    ingest_password_hash: str
    ingest_password_updated_at: datetime
    extra: Mapping[str, Any] = field(default_factory=dict)


__all__ = [
    "Job",
    "JobFailureReason",
    "JobStatus",
    "MediaObject",
    "ProcessingLog",
    "ProcessingStatus",
    "Settings",
    "Slot",
    "SlotRecentResult",
    "TemplateMedia",
]
