"""Data structures for ingest pipeline."""

from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


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
