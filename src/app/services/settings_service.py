"""Interface for global settings management used across the application."""

from __future__ import annotations

from datetime import datetime

from ..domain.models import Settings


class SettingsService:
    """Coordinates access to global configuration and ingest credentials."""

    def get_settings(self, *, force_refresh: bool = False) -> Settings:
        """Return the latest configuration snapshot.

        Implementations may cache results in memory. ``force_refresh``
        invalidates the cache and forces a repository read.
        """

        raise NotImplementedError

    def verify_ingest_password(self, password: str) -> bool:
        """Validate DSLR ingest credentials."""

        raise NotImplementedError

    def update_settings(self, payload: object, *, updated_by: str) -> Settings:
        """Persist administrator initiated configuration changes."""

        raise NotImplementedError

    def rotate_ingest_password(
        self,
        *,
        rotated_at: datetime,
        updated_by: str,
        new_password: str | None = None,
    ) -> tuple[Settings, str]:
        """Rotate the ingest password hash and return the plaintext secret."""

        raise NotImplementedError
