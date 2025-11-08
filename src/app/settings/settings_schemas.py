"""Pydantic schemas for settings admin API."""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field, conint


class ProviderKeyStatus(BaseModel):
    configured: bool
    updated_at: datetime | None = None


class SettingsResponseModel(BaseModel):
    sync_response_seconds: int
    result_ttl_hours: int
    ingest_password_rotated_at: datetime | None = None
    ingest_password_rotated_by: str | None = None
    provider_keys: dict[str, ProviderKeyStatus] = Field(default_factory=dict)


class SettingsUpdateRequest(BaseModel):
    sync_response_seconds: conint(ge=10, le=60) | None = None
    result_ttl_hours: conint(ge=24, le=168) | None = None
    ingest_password: str | None = Field(default=None, min_length=8, max_length=64)
    provider_keys: dict[str, str] | None = None
