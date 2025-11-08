"""Pydantic schemas for slot admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, conint


class SlotTemplateMediaPayload(BaseModel):
    media_kind: str = Field(..., min_length=1)
    media_object_id: str = Field(..., min_length=1)
    preview_url: str | None = None


class SlotRecentResultPayload(BaseModel):
    job_id: str
    status: str
    finished_at: datetime
    public_url: str
    expires_at: datetime | None = None


class SlotSummaryResponse(BaseModel):
    slot_id: str
    display_name: str
    provider: str
    operation: str
    is_active: bool
    version: int
    updated_at: datetime | None


class SlotDetailsResponse(SlotSummaryResponse):
    size_limit_mb: int
    sync_response_seconds: int
    settings: dict[str, Any]
    template_media: list[SlotTemplateMediaPayload]
    recent_results: list[SlotRecentResultPayload]


class SlotUpdateRequest(BaseModel):
    display_name: str
    provider: str
    operation: str
    is_active: bool
    size_limit_mb: conint(ge=1, le=20)
    sync_response_seconds: conint(ge=10, le=60) | None = None
    settings: dict[str, Any] = Field(default_factory=dict)
    template_media: list[SlotTemplateMediaPayload] = Field(default_factory=list)
