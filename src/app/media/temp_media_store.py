"""Temporary media storage for ingest uploads."""

from __future__ import annotations

import logging
import shutil
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import UploadFile

from ..config import MediaPaths
from ..repositories.media_object_repository import MediaObjectRepository

CHUNK_SIZE = 1 * 1024 * 1024  # 1 MiB


@dataclass(slots=True)
class TempMediaHandle:
    """Descriptor storing metadata about a temp media object."""

    media_id: str
    path: Path


@dataclass(slots=True)
class TempMediaStore:
    """Manages lifecycle of temporary ingest files."""

    paths: MediaPaths
    media_repo: MediaObjectRepository
    temp_ttl_seconds: int
    log: logging.Logger = field(default_factory=lambda: logging.getLogger(__name__))

    def temp_dir(self, slot_id: str, job_id: str) -> Path:
        return self.paths.temp / slot_id / job_id

    def ensure_structure(self, slot_id: str, job_id: str) -> Path:
        directory = self.temp_dir(slot_id, job_id)
        directory.mkdir(parents=True, exist_ok=True)
        return directory

    async def persist_upload(
        self,
        slot_id: str,
        job_id: str,
        upload: UploadFile,
        *,
        expires_at: datetime,
    ) -> TempMediaHandle:
        """Copy upload contents to temp storage and register metadata."""
        directory = self.ensure_structure(slot_id, job_id)
        target = directory / self._derive_filename(upload.filename)

        with target.open("wb") as sink:
            while True:
                chunk = await upload.read(CHUNK_SIZE)
                if not chunk:
                    break
                sink.write(chunk)
        await upload.seek(0)

        max_expires = datetime.utcnow() + timedelta(seconds=self.temp_ttl_seconds)
        lease_until = min(expires_at, max_expires)
        media_id = self.media_repo.register_temp(
            job_id=job_id,
            slot_id=slot_id,
            path=target,
            expires_at=lease_until,
        )
        self.log.info(
            "media.temp.persisted",
            extra={
                "slot_id": slot_id,
                "job_id": job_id,
                "media_id": media_id,
                "path": str(target),
                "expires_at": lease_until.isoformat(),
            },
        )
        return TempMediaHandle(media_id=media_id, path=target)

    def cleanup(self, slot_id: str, job_id: str, handles: list[TempMediaHandle]) -> None:
        """Remove temp directory and mark records cleaned."""
        if not handles:
            self._remove_directory(slot_id, job_id)
            return

        cleaned_at = datetime.utcnow()
        for handle in handles:
            try:
                self.media_repo.mark_cleaned(handle.media_id, cleaned_at)
            except KeyError:
                self.log.warning(
                    "media.temp.missing_record",
                    extra={"slot_id": slot_id, "job_id": job_id, "media_id": handle.media_id},
                )
        self._remove_directory(slot_id, job_id)

    def cleanup_expired(self, reference_time: datetime | None = None) -> int:
        """Purge temp media that exceeded TTL (fallback for cron)."""
        now = reference_time or datetime.utcnow()
        expired = self.media_repo.list_expired_by_scope("provider", now)
        removed = 0
        for media in expired:
            self._remove_single_path(media.path)
            self.media_repo.mark_cleaned(media.id, now)
            removed += 1
            self.log.info(
                "media.temp.cleanup.removed",
                extra={"media_id": media.id, "slot_id": media.slot_id, "job_id": media.job_id},
            )
        return removed

    def _remove_directory(self, slot_id: str, job_id: str) -> None:
        directory = self.temp_dir(slot_id, job_id)
        if directory.exists():
            shutil.rmtree(directory, ignore_errors=True)

    @staticmethod
    def _remove_single_path(path: Path) -> None:
        try:
            if path.is_file() or path.is_symlink():
                path.unlink(missing_ok=True)
            elif path.is_dir():
                shutil.rmtree(path, ignore_errors=True)
        except Exception:
            # Ignore unexpected failures to avoid blocking cron; deletion retried later.
            pass

    @staticmethod
    def _derive_filename(filename: str | None) -> str:
        if filename:
            suffix = Path(filename).suffix
            stem = Path(filename).stem or "upload"
            return f"{stem}{suffix}"
        return "upload.bin"
