"""Manage global application settings."""

from __future__ import annotations

import json
import os
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
    _snapshot: dict[str, Any] | None = None
    _legacy_ingest_password_hash: str | None = None

    def load(self) -> dict[str, Any]:
        """Return current snapshot merged with defaults and apply runtime settings."""
        store = self.repo.read_all()
        self._cache = store
        snapshot, legacy_hash, provider_values = self._hydrate(store)
        self._apply_runtime(snapshot, legacy_hash, provider_values)
        self._snapshot = snapshot
        return snapshot

    def snapshot(self) -> dict[str, Any]:
        """Return cached snapshot, loading from storage if necessary."""
        if self._snapshot is None:
            return self.load()
        return self._snapshot

    def update(
        self, payload: dict[str, Any], actor: str | None = None
    ) -> dict[str, Any]:
        """Persist changes (sync_response_seconds, result_ttl_hours, passwords, provider keys)."""
        store = self.repo.read_all()

        updates: dict[str, str] = {}

        if (value := payload.get("sync_response_seconds")) is not None:
            updates["sync_response_seconds"] = str(value)

        if (value := payload.get("result_ttl_hours")) is not None:
            updates["result_ttl_hours"] = str(value)

        if password := payload.get("ingest_password"):
            updates["ingest_password"] = password
            updates["ingest_password_rotated_at"] = datetime.utcnow().isoformat()
            updates["ingest_password_rotated_by"] = actor or "admin-ui"

        if provider_keys := payload.get("provider_keys"):
            existing = json.loads(store.get("provider_keys", "{}") or "{}")
            now = datetime.utcnow().isoformat()
            for provider, key in provider_keys.items():
                existing[provider] = {"value": key, "updated_at": now}
            updates["provider_keys"] = json.dumps(existing)

        if updates:
            self.repo.bulk_upsert(updates, updated_by=actor)

        merged = self.repo.read_all()
        self._cache = merged
        snapshot, legacy_hash, provider_values = self._hydrate(merged)
        self._apply_runtime(snapshot, legacy_hash, provider_values)
        self._snapshot = snapshot
        return snapshot

    def _hydrate(
        self, store: dict[str, str]
    ) -> tuple[dict[str, Any], str | None, dict[str, str]]:
        def int_or_default(key: str, default: int) -> int:
            try:
                value = store.get(key)
                if value is None:
                    return default
                return int(value)
            except (TypeError, ValueError):
                return default

        sync_response_seconds = int_or_default(
            "sync_response_seconds", self.config.sync_response_seconds
        )
        result_ttl_hours = int_or_default(
            "result_ttl_hours", self.config.result_ttl_hours
        )
        ingest_password_rotated_at = store.get("ingest_password_rotated_at")
        ingest_password_rotated_by = store.get("ingest_password_rotated_by")
        ingest_password = store.get("ingest_password", self.config.ingest_password)
        if ingest_password is None:
            ingest_password = ""

        ingest_password_hash = store.get("ingest_password_hash")

        provider_keys_raw = store.get("provider_keys", "{}") or "{}"
        try:
            provider_store = json.loads(provider_keys_raw)
        except json.JSONDecodeError:
            provider_store = {}

        provider_statuses: dict[str, dict[str, Any]] = {}
        provider_values: dict[str, str] = {}
        for name, data in provider_store.items():
            value = data.get("value")
            if isinstance(value, str) and value:
                provider_values[name] = value
            provider_statuses[name] = {
                "configured": bool(value),
                "updated_at": _parse_datetime(data.get("updated_at")),
            }

        return (
            {
                "sync_response_seconds": sync_response_seconds,
                "result_ttl_hours": result_ttl_hours,
                "ingest_password": ingest_password,
                "ingest_password_rotated_at": _parse_datetime(
                    ingest_password_rotated_at
                ),
                "ingest_password_rotated_by": ingest_password_rotated_by,
                "provider_keys": provider_statuses,
            },
            ingest_password_hash,
            provider_values,
        )


    def _apply_runtime(
        self,
        snapshot: dict[str, Any],
        legacy_ingest_password_hash: str | None,
        provider_values: dict[str, str],
    ) -> None:
        """Propagate stored values to services/config so API reflects real state."""
        self.ingest_service.sync_response_seconds = snapshot["sync_response_seconds"]
        self.ingest_service.result_ttl_hours = snapshot["result_ttl_hours"]
        self.ingest_service.ingest_password = snapshot["ingest_password"]
        self.ingest_service.ingest_password_hash = legacy_ingest_password_hash
        self._legacy_ingest_password_hash = legacy_ingest_password_hash

        self.config.sync_response_seconds = snapshot["sync_response_seconds"]
        self.config.result_ttl_hours = snapshot["result_ttl_hours"]
        self.config.ingest_password = snapshot["ingest_password"]

        env_map = {
            "gemini": "GEMINI_API_KEY",
            "gemini-3-pro": "GEMINI_API_KEY",
            "gpt-image-1.5": "OPENAI_API_KEY",
            "turbotext": "TURBOTEXT_API_KEY",
        }
        for provider, value in provider_values.items():
            env_key = env_map.get(provider)
            if env_key and value:
                os.environ[env_key] = value


def _parse_datetime(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        return None
