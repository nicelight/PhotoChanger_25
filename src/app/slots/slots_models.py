"""Slot domain dataclass."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class Slot:
    id: str
    provider: str
    operation: str
    display_name: str
    settings: dict[str, Any] = field(default_factory=dict)
    size_limit_mb: int = 15
    is_active: bool = True
    version: int = 1
    updated_by: str | None = None
    template_media: list["SlotTemplateMedia"] = field(default_factory=list)
    updated_at: datetime | None = None


@dataclass(slots=True)
class SlotTemplateMedia:
    id: str
    slot_id: str
    media_kind: str
    media_object_id: str
    role: str | None = None
