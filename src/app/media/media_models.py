"""Media data models."""

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


@dataclass(slots=True)
class MediaObject:
    id: str
    job_id: str
    slot_id: str
    path: Path
    preview_path: Path | None
    expires_at: datetime
    scope: str
    cleaned_at: datetime | None = None
