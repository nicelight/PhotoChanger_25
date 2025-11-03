"""Manage global application settings."""

from dataclasses import dataclass


@dataclass(slots=True)
class SettingsService:
    """Provide read/write access to global settings (stub)."""

    repo: "SettingsRepository"

    def read(self) -> dict:
        """Return settings dictionary."""
        return self.repo.read()
