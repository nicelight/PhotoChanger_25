"""Pydantic schemas for slot admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field


class SlotTemplateMediaPayload(BaseModel):
    media_kind: str = Field(..., min_length=1)
    media_object_id: str = Field(..., min_length=1)
    role: str = Field(..., min_length=1)
    preview_url: str | None = None


class SlotRecentResultPayload(BaseModel):
    job_id: str
    status: str
    finished_at: datetime
    public_url: str
    download_url: str | None = None
    thumbnail_url: str | None = None
    result_expires_at: datetime | None = None
    mime: str | None = None
    expires_at: datetime | None = None  # deprecated alias for result_expires_at


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
    latest_result: SlotRecentResultPayload | None = None


class SlotUpdateRequest(BaseModel):
    display_name: str
    provider: str
    operation: str
    is_active: bool
    size_limit_mb: int = Field(..., ge=1, le=20)
    sync_response_seconds: int | None = Field(default=None, ge=10, le=60)
    settings: dict[str, Any] = Field(default_factory=dict)
    template_media: list[SlotTemplateMediaPayload] = Field(default_factory=list)
