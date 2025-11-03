"""Domain service for ingest operations."""

from __future__ import annotations

import logging
import uuid
from pathlib import Path
from dataclasses import dataclass, field
from datetime import datetime, timedelta

from fastapi import UploadFile

from ..repositories.job_history_repository import JobHistoryRepository
from ..repositories.media_object_repository import MediaObjectRepository
from ..slots.slots_repository import SlotRepository
from ..media.media_service import ResultStore
from .ingest_errors import ChecksumMismatchError
from .ingest_models import JobContext, UploadValidationResult
from .validation import UploadValidator

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class IngestService:
    """Coordinates ingest workflow."""

    slot_repo: SlotRepository
    validator: UploadValidator
    job_repo: JobHistoryRepository
    media_repo: MediaObjectRepository
    result_store: "ResultStore"
    result_ttl_hours: int
    sync_response_seconds: int
    log: logging.Logger = field(default_factory=lambda: logger)

    def prepare_job(self, slot_id: str) -> JobContext:
        """Initialize context using slot configuration and persist pending job."""
        slot = self.slot_repo.get_slot(slot_id)
        job_id = uuid.uuid4().hex
        started_at = datetime.utcnow()
        sync_deadline = started_at + timedelta(seconds=self.sync_response_seconds)

        self.job_repo.create_pending(
            job_id=job_id,
            slot_id=slot.id,
            started_at=started_at,
            sync_deadline=sync_deadline,
        )

        result_dir = self.result_store.ensure_structure(slot.id, job_id)
        result_expires_at = started_at + timedelta(hours=self.result_ttl_hours)

        job = JobContext(
            slot_id=slot.id,
            job_id=job_id,
            sync_deadline=sync_deadline,
            result_dir=result_dir,
            result_expires_at=result_expires_at,
        )
        job.metadata["provider"] = slot.provider
        job.metadata["size_limit_mb"] = str(slot.size_limit_mb)
        return job

    async def validate_upload(
        self,
        job: JobContext,
        upload: UploadFile,
        expected_hash: str,
    ) -> UploadValidationResult:
        slot = self.slot_repo.get_slot(job.slot_id)
        result = await self.validator.validate(slot.size_limit_mb, upload)

        if result.sha256.lower() != expected_hash.lower():
            self.log.warning(
                "ingest.upload.checksum_mismatch",
                extra={
                    "slot_id": job.slot_id,
                    "job_id": job.job_id,
                    "expected_hash": expected_hash,
                    "calculated_hash": result.sha256,
                },
            )
            raise ChecksumMismatchError("Checksum mismatch")

        job.upload = result
        self.log.info(
            "ingest.upload.ready",
            extra={
                "slot_id": job.slot_id,
                "job_id": job.job_id,
                "size_bytes": result.size_bytes,
                "content_type": result.content_type,
            },
        )
        return result

    def record_success(
        self,
        job: JobContext,
        payload: bytes,
        content_type: str,
    ) -> Path:
        """Persist successful result to disk and DB."""
        if job.job_id is None or job.result_dir is None:
            raise RuntimeError("JobContext is not fully initialized")

        extension = self._extension_from_content_type(content_type)
        payload_path = self.result_store.save_payload(job.slot_id, job.job_id, payload, extension)

        expires_at = job.result_expires_at or (datetime.utcnow() + timedelta(hours=self.result_ttl_hours))
        self.job_repo.set_result(
            job_id=job.job_id,
            status="done",
            result_path=str(payload_path),
            result_expires_at=expires_at,
        )
        self.media_repo.register_result(
            job_id=job.job_id,
            slot_id=job.slot_id,
            path=payload_path,
            preview_path=None,
            expires_at=expires_at,
        )
        self.log.info(
            "ingest.job.completed",
            extra={"slot_id": job.slot_id, "job_id": job.job_id, "result_path": str(payload_path)},
        )
        return payload_path

    def record_failure(
        self,
        job: JobContext,
        failure_reason: str,
        status: str = "failed",
    ) -> None:
        """Update job status and cleanup result dir on failure/timeout."""
        if job.job_id is None:
            raise RuntimeError("JobContext is not fully initialized")
        self.job_repo.set_failure(job_id=job.job_id, status=status, failure_reason=failure_reason)
        self.result_store.remove_result_dir(job.slot_id, job.job_id)
        self.log.warning(
            "ingest.job.failed",
            extra={"slot_id": job.slot_id, "job_id": job.job_id, "reason": failure_reason, "status": status},
        )

    async def process(self, job: JobContext) -> bytes:  # pragma: no cover - placeholder
        raise NotImplementedError

    @staticmethod
    def _extension_from_content_type(content_type: str) -> str:
        mapping = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        return mapping.get(content_type, "bin")
