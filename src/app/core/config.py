"""Application configuration scaffolding for PhotoChanger.

The defaults mirror the blueprint expectations: ``T_sync_response`` equals
48 секунд, public media is stored under ``MEDIA_ROOT`` and PostgreSQL acts
as the primary queue. Real secrets are injected via environment variables;
during scaffolding we keep deterministic placeholders.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, cast

from pydantic import Field

try:  # pragma: no cover - optional dependency bridge
    from pydantic_settings import BaseSettings as _BaseSettings
except ImportError:  # pragma: no cover - fallback when pydantic-settings missing
    from pydantic import BaseSettings as _BaseSettings  # type: ignore


def _settings_config(**config: Any) -> dict[str, Any]:
    """Return a mapping compatible with ``BaseSettings.model_config``."""

    return dict(config)


BaseSettings = _BaseSettings


def _default_media_root() -> Path:
    """Return the default media directory described in the SDD."""

    return Path("./var/media")


class AppConfig(BaseSettings):
    """Pydantic settings container for the service layer."""

    model_config = cast(Any, _settings_config(env_prefix="PHOTOCHANGER_"))

    database_url: str = Field(
        default="postgresql://localhost:5432/photochanger",
        description="Connection string for the primary PostgreSQL queue",
    )
    queue_statement_timeout_ms: int = Field(
        default=5_000,
        ge=1_000,
        description="PostgreSQL statement_timeout used by the job queue (ms).",
    )
    queue_max_in_flight_jobs: int = Field(
        default=12,
        ge=1,
        description=(
            "Upper bound on concurrently active jobs before ingest applies back-pressure."
        ),
    )
    media_root: Path = Field(
        default_factory=_default_media_root,
        description="Filesystem root for MEDIA_ROOT artefacts.",
    )
    t_sync_response_seconds: int = Field(
        default=48,
        ge=45,
        le=60,
        description="Default synchronous deadline (T_sync_response) in seconds.",
    )
    jwt_secret: str = Field(
        default="change-me",
        min_length=1,
        description="Placeholder secret used for JWT generation during scaffolding.",
    )
    provider_keys: Dict[str, str] = Field(
        default_factory=dict,
        description="Mapping of provider identifiers to configured API keys.",
    )

    @classmethod
    def build_default(cls) -> "AppConfig":
        """Construct configuration with blueprint-aligned defaults."""

        return cls()


__all__ = ["AppConfig"]
