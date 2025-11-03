"""Data structures for ingest pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - type checking only
    from ..media.temp_media_store import TempMediaHandle


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
    sync_deadline: datetime | None = None
    result_dir: Path | None = None
    result_expires_at: datetime | None = None
    upload: UploadValidationResult | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    temp_media: list["TempMediaHandle"] = field(default_factory=list)
    temp_payload_path: Path | None = None
