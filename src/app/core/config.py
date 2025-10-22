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
    stats_database_url: str | None = Field(
        default=None,
        description="Optional dedicated PostgreSQL DSN for statistics aggregation.",
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
    stats_slot_cache_ttl_seconds: int = Field(
        default=5 * 60,
        ge=0,
        description="TTL for per-slot statistics cache entries in seconds.",
    )
    stats_global_cache_ttl_seconds: int = Field(
        default=60,
        ge=0,
        description="TTL for global statistics cache entries in seconds.",
    )
    stats_recent_results_retention_hours: int = Field(
        default=72,
        ge=1,
        description="Retention horizon for recent results cache in hours.",
    )
    stats_recent_results_limit: int = Field(
        default=10,
        ge=1,
        description="Maximum number of recent results entries returned per slot.",
    )
    worker_poll_interval_ms: int = Field(
        default=1_000,
        ge=10,
        description="Polling interval for QueueWorker.run_forever in milliseconds.",
    )
    worker_max_poll_attempts: int = Field(
        default=10,
        ge=1,
        description="Maximum sequential polling attempts before the worker idles.",
    )
    worker_retry_attempts: int = Field(
        default=5,
        ge=1,
        description="Number of retry attempts for provider dispatch failures.",
    )
    worker_retry_backoff_seconds: float = Field(
        default=3.0,
        ge=0.0,
        description="Base delay between provider retry attempts in seconds.",
    )
    worker_request_timeout_seconds: float = Field(
        default=5.0,
        ge=0.1,
        description="Timeout applied to provider requests in seconds.",
    )

    @classmethod
    def build_default(cls) -> "AppConfig":
        """Construct configuration with blueprint-aligned defaults."""

        return cls()


__all__ = ["AppConfig"]
