"""Media service interface coordinating payloads and public links."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from ..domain.models import MediaObject, Settings


class MediaService:
    """High-level operations over ingest payloads and result media."""

    def register_media(
        self,
        *,
        path: str,
        mime: str,
        size_bytes: int,
        expires_at: datetime,
        job_id: UUID | None = None,
    ) -> MediaObject:
        """Register a new media object stored in MEDIA_ROOT.

        Callers must calculate ``expires_at`` via
        ``min(job.expires_at, now + T_public_link_ttl)`` where
        ``T_public_link_ttl = T_sync_response`` as mandated by the SDD.
        """

        raise NotImplementedError

    def get_media_by_path(self, path: str) -> MediaObject | None:
        """Return registered media metadata for ``MEDIA_ROOT`` relative ``path``."""

        raise NotImplementedError

    def save_result_media(
        self,
        *,
        job_id: UUID,
        data: bytes,
        mime: str,
        finalized_at: datetime,
        retention_hours: int,
        suggested_name: str | None = None,
    ) -> tuple[MediaObject, str]:
        """Persist processed result bytes and register the media object.

        Implementations must store ``data`` under ``MEDIA_ROOT/results`` using a
        deterministic filename derived from ``job_id`` and ``suggested_name`` or
        ``mime``. The returned tuple contains the registered media object and
        the SHA-256 checksum of the stored payload. ``media.expires_at`` must be
        calculated as ``finalized_at + retention_hours`` (72h per ADR-0002).
        """

        raise NotImplementedError

    def refresh_public_link(
        self, media: MediaObject, settings: Settings
    ) -> MediaObject:
        """Re-issue ``media.public_url`` with TTL = ``T_sync_response``.

        Implementations must reuse settings from ``Settings.media_cache`` and
        ensure the refreshed TTL never exceeds the associated job's
        ``expires_at`` (when a job is linked to the media object).
        """

        raise NotImplementedError

    def revoke_media(self, media: MediaObject) -> None:
        """Remove public access to an object immediately."""

        raise NotImplementedError

    def purge_expired_media(self, *, now: datetime) -> list[MediaObject]:
        """Return and purge objects whose TTL elapsed."""

        raise NotImplementedError
