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
        """Register a new media object stored in MEDIA_ROOT."""

        raise NotImplementedError

    def refresh_public_link(
        self, media: MediaObject, settings: Settings
    ) -> MediaObject:
        """Re-issue a public link with TTL = ``T_sync_response``."""

        raise NotImplementedError

    def revoke_media(self, media: MediaObject) -> None:
        """Remove public access to an object immediately."""

        raise NotImplementedError

    def purge_expired_media(self, *, now: datetime) -> list[MediaObject]:
        """Return and purge objects whose TTL elapsed."""

        raise NotImplementedError
