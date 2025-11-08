"""Domain service for ingest operations."""

from __future__ import annotations

import asyncio
import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from fastapi import UploadFile

from ..providers.providers_base import ProviderDriver, ProviderResult
from ..providers.providers_factory import create_driver
from ..repositories.job_history_repository import JobHistoryRepository
from ..repositories.media_object_repository import MediaObjectRepository
from ..slots.slots_repository import SlotRepository
from ..media.media_service import ResultStore
from ..media.temp_media_store import TempMediaStore
from .ingest_errors import (
    ChecksumMismatchError,
    PayloadTooLargeError,
    ProviderExecutionError,
    ProviderTimeoutError,
    UnsupportedMediaError,
    UploadReadError,
)
from .ingest_models import FailureReason, JobContext, JobStatus, UploadValidationResult
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
    temp_store: "TempMediaStore"
    result_ttl_hours: int
    sync_response_seconds: int
    provider_factory: Callable[[str], ProviderDriver] = field(default_factory=lambda: create_driver)
    log: logging.Logger = field(default_factory=lambda: logger)

    def prepare_job(self, slot_id: str, *, source: str = "ingest") -> JobContext:
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
            source=source,
        )

        result_dir = self.result_store.ensure_structure(slot.id, job_id)
        result_expires_at = started_at + timedelta(hours=self.result_ttl_hours)

        job = JobContext(
            slot_id=slot.id,
            job_id=job_id,
            slot_settings=slot.settings,
            slot_template_media={media.media_kind: media.media_object_id for media in slot.template_media},
            slot_version=slot.version,
            sync_deadline=sync_deadline,
            result_dir=result_dir,
            result_expires_at=result_expires_at,
        )
        job.metadata["provider"] = slot.provider
        job.metadata["size_limit_mb"] = str(slot.size_limit_mb)
        job.metadata["slot_version"] = str(slot.version)
        if slot.updated_by:
            job.metadata["slot_updated_by"] = slot.updated_by
        job.metadata["slot_display_name"] = slot.display_name
        job.metadata["source"] = source
        return job

    async def validate_upload(
        self,
        job: JobContext,
        upload: UploadFile,
        expected_hash: str | None,
    ) -> UploadValidationResult:
        slot = self.slot_repo.get_slot(job.slot_id)
        job.slot_settings = slot.settings
        job.slot_template_media = {media.media_kind: media.media_object_id for media in slot.template_media}
        job.slot_version = slot.version
        result = await self.validator.validate(slot.size_limit_mb, upload)

        if expected_hash is not None and result.sha256.lower() != expected_hash.lower():
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

        if job.job_id is None or job.sync_deadline is None:
            raise RuntimeError("JobContext missing identifiers for temp storage")

        handle = await self.temp_store.persist_upload(
            slot_id=job.slot_id,
            job_id=job.job_id,
            upload=upload,
            expires_at=job.sync_deadline,
        )
        job.temp_media.append(handle)
        job.temp_payload_path = handle.path

        self.log.info(
            "ingest.upload.ready",
            extra={
                "slot_id": job.slot_id,
                "job_id": job.job_id,
                "size_bytes": result.size_bytes,
                "content_type": result.content_type,
                "temp_path": str(handle.path),
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
            status=JobStatus.DONE.value,
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
        self.temp_store.cleanup(job.slot_id, job.job_id, job.temp_media)
        self.log.info(
            "ingest.job.completed",
            extra={"slot_id": job.slot_id, "job_id": job.job_id, "result_path": str(payload_path)},
        )
        return payload_path

    def record_failure(
        self,
        job: JobContext,
        failure_reason: FailureReason | str,
        status: JobStatus = JobStatus.FAILED,
    ) -> None:
        """Update job status and cleanup result dir on failure/timeout."""
        if job.job_id is None:
            raise RuntimeError("JobContext is not fully initialized")
        reason = failure_reason.value if isinstance(failure_reason, FailureReason) else failure_reason
        self.job_repo.set_failure(
            job_id=job.job_id,
            status=status.value,
            failure_reason=reason,
        )
        self.result_store.remove_result_dir(job.slot_id, job.job_id)
        self.temp_store.cleanup(job.slot_id, job.job_id, job.temp_media)
        self.log.warning(
            "ingest.job.failed",
            extra={
                "slot_id": job.slot_id,
                "job_id": job.job_id,
                "reason": reason,
                "status": status.value,
            },
        )

    async def run_test_job(
        self,
        slot_id: str,
        upload: UploadFile,
        *,
        overrides: dict[str, Any] | None = None,
        expected_hash: str | None = None,
    ) -> tuple[JobContext, float]:
        """Execute validate+process flow for admin test runs."""
        job = self.prepare_job(slot_id, source="ui_test")
        started_at = datetime.utcnow()

        try:
            await self.validate_upload(job, upload, expected_hash)
        except UnsupportedMediaError:
            self.record_failure(job, FailureReason.UNSUPPORTED_MEDIA_TYPE)
            raise
        except PayloadTooLargeError:
            self.record_failure(job, FailureReason.PAYLOAD_TOO_LARGE)
            raise
        except (ChecksumMismatchError, UploadReadError):
            self.record_failure(job, FailureReason.INVALID_REQUEST)
            raise

        if overrides:
            self._apply_test_overrides(job, overrides)

        await self.process(job)
        duration = (datetime.utcnow() - started_at).total_seconds()
        return job, duration

    async def process(self, job: JobContext) -> bytes:
        """Invoke provider driver with timeout and persist result."""
        if job.job_id is None:
            raise RuntimeError("JobContext is not fully initialized")

        provider_name = job.metadata.get("provider", "unknown")
        started_at = datetime.utcnow()
        try:
            payload, content_type = await asyncio.wait_for(
                self._invoke_provider(job),
                timeout=self.sync_response_seconds,
            )
        except asyncio.TimeoutError as exc:
            duration = (datetime.utcnow() - started_at).total_seconds()
            self.log.warning(
                "ingest.job.timeout",
                extra={
                    "slot_id": job.slot_id,
                    "job_id": job.job_id,
                    "provider": provider_name,
                    "timeout_seconds": self.sync_response_seconds,
                    "duration_seconds": duration,
                },
            )
            self.record_failure(job, FailureReason.PROVIDER_TIMEOUT, status=JobStatus.TIMEOUT)
            raise ProviderTimeoutError("Provider did not finish in time") from exc
        except ProviderExecutionError as exc:
            duration = (datetime.utcnow() - started_at).total_seconds()
            self.log.error(
                "ingest.job.provider_error",
                extra={
                    "slot_id": job.slot_id,
                    "job_id": job.job_id,
                    "provider": provider_name,
                    "duration_seconds": duration,
                    "error": str(exc),
                },
            )
            self.record_failure(job, FailureReason.PROVIDER_ERROR)
            raise

        self.record_success(job, payload, content_type)
        return payload

    async def _invoke_provider(self, job: JobContext) -> tuple[bytes, str]:  # pragma: no cover - to be implemented
        provider_name = job.metadata.get("provider")
        if not provider_name:
            raise ProviderExecutionError("Provider is not specified for the job")

        try:
            driver = self.provider_factory(provider_name)
        except Exception as exc:
            raise ProviderExecutionError(f"Unsupported provider '{provider_name}'") from exc

        try:
            result = await driver.process(job)
        except Exception as exc:
            raise ProviderExecutionError(f"Provider '{provider_name}' failed to process job") from exc

        if not isinstance(result, ProviderResult):
            raise ProviderExecutionError(f"Provider '{provider_name}' returned invalid result")

        content_type = result.content_type or (
            job.upload.content_type if job.upload and job.upload.content_type else "image/png"
        )
        return result.payload, content_type

    @staticmethod
    def _extension_from_content_type(content_type: str) -> str:
        mapping = {
            "image/jpeg": "jpg",
            "image/png": "png",
            "image/webp": "webp",
        }
        return mapping.get(content_type, "bin")

    def _apply_test_overrides(self, job: JobContext, overrides: dict[str, Any]) -> None:
        """Apply prompt/provider/template overrides for admin test runs."""
        provider = overrides.get("provider")
        if isinstance(provider, str) and provider:
            job.metadata["provider"] = provider

        operation = overrides.get("operation")
        if isinstance(operation, str) and operation:
            job.metadata["operation"] = operation

        settings_override = overrides.get("settings")
        if isinstance(settings_override, dict):
            merged = dict(job.slot_settings or {})
            merged.update(settings_override)
            job.slot_settings = merged

        template_overrides = overrides.get("template_media")
        if isinstance(template_overrides, list):
            job.slot_settings["template_media"] = template_overrides
            template_map = {}
            for item in template_overrides:
                if not isinstance(item, dict):
                    continue
                media_kind = item.get("media_kind")
                media_object_id = item.get("media_object_id")
                if media_kind and media_object_id:
                    template_map[str(media_kind)] = str(media_object_id)
            if template_map:
                job.slot_template_media = template_map
