"""Helpers for serving media objects to external consumers (e.g., providers)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from fastapi import HTTPException, status
from fastapi.responses import FileResponse

from ..repositories.media_object_repository import MediaObjectRepository


@dataclass(slots=True)
class PublicMediaService:
    """Expose media files for short-lived external access."""

    media_repo: MediaObjectRepository

    def open_media(self, media_id: str) -> FileResponse:
        """Return FileResponse for media_id or raise HTTP errors."""
        try:
            media = self.media_repo.get_media(media_id)
        except KeyError as exc:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found") from exc

        if media.scope != "provider":
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Media not found")

        if media.expires_at and media.expires_at < datetime.utcnow():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Media expired")

        path: Path = media.path
        if not path.exists():
            raise HTTPException(status_code=status.HTTP_410_GONE, detail="Media file missing")

        return FileResponse(
            path=path,
            media_type=_guess_mime(path.suffix),
            filename=path.name,
        )


def _guess_mime(suffix: str) -> str:
    lowered = suffix.lower()
    if lowered in {".jpg", ".jpeg"}:
        return "image/jpeg"
    if lowered == ".png":
        return "image/png"
    if lowered == ".webp":
        return "image/webp"
    return "application/octet-stream"
