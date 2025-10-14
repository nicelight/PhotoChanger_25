"""Application settings service interface."""

from __future__ import annotations

from datetime import datetime

from ..domain.models import Settings


class SettingsService:
    """Coordinates read/write operations for global application settings."""

    def read_settings(self) -> Settings:
        """Return current configuration, including TTL definitions."""

        raise NotImplementedError

    def update_settings(self, settings: Settings) -> Settings:
        """Persist configuration changes coming from the admin UI."""

        raise NotImplementedError

    def rotate_ingest_password(
        self, *, rotated_at: datetime, new_password: str | None = None
    ) -> Settings:
        """Rotate the ingest password hash and update audit timestamps."""

        raise NotImplementedError
