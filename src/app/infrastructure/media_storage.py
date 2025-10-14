"""Abstractions over media storage backends."""

from __future__ import annotations

from datetime import datetime
from typing import BinaryIO
from uuid import UUID

from ..domain.models import MediaObject


class MediaStorage:
    """Low-level persistence API for ingest and result files."""

    def store_payload(
        self,
        *,
        job_id: UUID,
        payload: BinaryIO,
        mime: str,
        expires_at: datetime,
    ) -> MediaObject:
        """Persist an ingest payload with TTL tied to ``T_sync_response``."""

        raise NotImplementedError

    def store_result(
        self,
        *,
        job_id: UUID,
        content: BinaryIO,
        mime: str,
        retention_expires_at: datetime,
    ) -> MediaObject:
        """Persist a final result with 72h retention."""

        raise NotImplementedError

    def generate_public_url(self, media: MediaObject) -> str:
        """Return a temporary public URL for the stored object."""

        raise NotImplementedError

    def delete_media(self, media: MediaObject) -> None:
        """Remove the object from storage immediately."""

        raise NotImplementedError

