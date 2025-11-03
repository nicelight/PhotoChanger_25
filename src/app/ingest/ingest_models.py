"""Data structures for ingest pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..media.temp_media_store import TempMediaHandle


class JobStatus(StrEnum):
    """Lifecycle statuses for job_history records."""

    PENDING = "pending"
    DONE = "done"
    TIMEOUT = "timeout"
    FAILED = "failed"


class FailureReason(StrEnum):
    """Failure reasons enumerated in ingest error contracts."""

    INVALID_REQUEST = "invalid_request"
    INVALID_PASSWORD = "invalid_password"
    SLOT_NOT_FOUND = "slot_not_found"
    SLOT_DISABLED = "slot_disabled"
    PAYLOAD_TOO_LARGE = "payload_too_large"
    UNSUPPORTED_MEDIA_TYPE = "unsupported_media_type"
    RATE_LIMITED = "rate_limited"
    PROVIDER_TIMEOUT = "provider_timeout"
    PROVIDER_ERROR = "provider_error"
    INTERNAL_ERROR = "internal_error"


@dataclass(slots=True)
class UploadValidationResult:
    """Outcome of validating an uploaded image."""

    content_type: str
    size_bytes: int
    sha256: str
    filename: str


@dataclass(slots=True)
class JobContext:
    """Aggregated data needed across ingest workflow."""

    slot_id: str
    job_id: str | None = None
    slot_settings: dict[str, Any] = field(default_factory=dict)
    slot_template_media: dict[str, str] = field(default_factory=dict)
    slot_version: int = 1
    sync_deadline: datetime | None = None
    result_dir: Path | None = None
    result_expires_at: datetime | None = None
    upload: UploadValidationResult | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    temp_media: list["TempMediaHandle"] = field(default_factory=list)
    temp_payload_path: Path | None = None
