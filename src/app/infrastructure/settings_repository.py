"""Repository responsible for reading and writing application settings."""

from __future__ import annotations

from datetime import datetime

from ..domain.models import Settings


class SettingsRepository:
    """Gateway to the ``app_settings`` persistence layer."""

    def load(self) -> Settings:
        """Read the current settings snapshot."""

        raise NotImplementedError

    def save(self, settings: Settings) -> Settings:
        """Persist updated TTL and provider configuration values."""

        raise NotImplementedError

    def update_ingest_password(
        self, *, rotated_at: datetime, password_hash: str
    ) -> Settings:
        """Store a new ingest password hash with audit timestamp."""

        raise NotImplementedError
