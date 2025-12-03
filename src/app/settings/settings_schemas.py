"""Pydantic schemas for settings admin API."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field


class ProviderKeyStatus(BaseModel):
    configured: bool
    updated_at: datetime | None = None


class SettingsResponseModel(BaseModel):
    sync_response_seconds: int
    result_ttl_hours: int
    ingest_password: str
    ingest_password_rotated_at: datetime | None = None
    ingest_password_rotated_by: str | None = None
    provider_keys: dict[str, ProviderKeyStatus] = Field(default_factory=dict)


class SettingsUpdateRequest(BaseModel):
    sync_response_seconds: int | None = Field(default=None, ge=10, le=60)
    result_ttl_hours: int | None = Field(default=None, ge=24, le=168)
    ingest_password: str | None = Field(default=None, min_length=8, max_length=64)
    provider_keys: dict[str, str] | None = None
