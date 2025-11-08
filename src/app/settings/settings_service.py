"""Manage global application settings."""

from __future__ import annotations

import json
import hashlib
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from ..config import AppConfig
from ..ingest.ingest_service import IngestService
from .settings_repository import SettingsRepository


@dataclass(slots=True)
class SettingsService:
    """Provide read/write access to global settings stored in DB."""

    repo: SettingsRepository
    ingest_service: IngestService
    config: AppConfig
    _cache: dict[str, str] = field(default_factory=dict)

    def load(self) -> dict[str, Any]:
        """Return current snapshot merged with defaults."""
        store = self.repo.read_all()
        self._cache = store
        return self._hydrate(store)

    def update(self, payload: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        """Persist changes (sync_response_seconds, result_ttl_hours, passwords, provider keys)."""
        store = self.repo.read_all()

        updates: dict[str, str] = {}

        if (value := payload.get("sync_response_seconds")) is not None:
            updates["sync_response_seconds"] = str(value)
            self.ingest_service.sync_response_seconds = value

        if (value := payload.get("result_ttl_hours")) is not None:
            updates["result_ttl_hours"] = str(value)
            self.ingest_service.result_ttl_hours = value

        if (password := payload.get("ingest_password")):
            hashed = hashlib.sha256(password.encode("utf-8")).hexdigest()
            updates["ingest_password_hash"] = hashed
            updates["ingest_password_rotated_at"] = datetime.utcnow().isoformat()
            updates["ingest_password_rotated_by"] = actor or "admin-ui"

        if (provider_keys := payload.get("provider_keys")):
            existing = json.loads(store.get("provider_keys", "{}") or "{}")
            now = datetime.utcnow().isoformat()
            for provider, key in provider_keys.items():
                existing[provider] = {"value": key, "updated_at": now}
            updates["provider_keys"] = json.dumps(existing)

        if updates:
            self.repo.bulk_upsert(updates, updated_by=actor)

        merged = self.repo.read_all()
        self._cache = merged
        return self._hydrate(merged)

    def _hydrate(self, store: dict[str, str]) -> dict[str, Any]:
        def int_or_default(key: str, default: int) -> int:
            try:
                return int(store.get(key, default))
            except (TypeError, ValueError):
                return default

        sync_response_seconds = int_or_default("sync_response_seconds", self.config.sync_response_seconds)
        result_ttl_hours = int_or_default("result_ttl_hours", self.config.result_ttl_hours)
        ingest_password_rotated_at = store.get("ingest_password_rotated_at")
        ingest_password_rotated_by = store.get("ingest_password_rotated_by")

        provider_keys_raw = store.get("provider_keys", "{}") or "{}"
        try:
            provider_store = json.loads(provider_keys_raw)
        except json.JSONDecodeError:
            provider_store = {}

        provider_statuses: dict[str, dict[str, Any]] = {}
        for name, data in provider_store.items():
            provider_statuses[name] = {
                "configured": bool(data.get("value")),
                "updated_at": _parse_datetime(data.get("updated_at")),
            }

        return {
            "sync_response_seconds": sync_response_seconds,
            "result_ttl_hours": result_ttl_hours,
            "ingest_password_rotated_at": _parse_datetime(ingest_password_rotated_at),
            "ingest_password_rotated_by": ingest_password_rotated_by,
            "provider_keys": provider_statuses,
        }


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
