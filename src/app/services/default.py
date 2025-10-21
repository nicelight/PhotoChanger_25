"""Default service implementations used during the ingest phase."""

from __future__ import annotations

import hashlib
import mimetypes
from dataclasses import dataclass, field, replace
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Iterable, Mapping
from uuid import UUID, uuid4

from ..core.config import AppConfig
from ..domain import calculate_job_expires_at, calculate_result_expires_at
from ..domain.models import (
    Job,
    JobFailureReason,
    JobStatus,
    MediaObject,
    MediaCacheSettings,
    ProcessingLog,
    Settings,
    SettingsDslrPasswordStatus,
    SettingsIngestConfig,
    Slot,
)
from ..infrastructure.queue.postgres import PostgresJobQueue
from ..infrastructure.settings_repository import SettingsRepository
from ..security import SecurityService
from .job_service import JobService, QueueBusyError, QueueUnavailableError
from .media_service import MediaService
from .settings import SettingsService
from .slot_service import SlotService
from .stats_service import StatsService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class InMemoryAuditLogger:
    """Collect audit events in memory for scaffolding environments."""

    records: list[dict[str, object]] = field(default_factory=list)

    def log(self, *, action: str, actor: str, details: Mapping[str, object]) -> None:
        self.records.append(
            {"action": action, "actor": actor, "details": dict(details)}
        )


@dataclass(slots=True)
class InMemorySettingsRepository(SettingsRepository):
    """Minimal in-memory implementation of :class:`SettingsRepository`."""

    settings: Settings
    password_hash: str

    def load(self) -> Settings:
        return self.settings

    def save(self, settings: Settings) -> Settings:
        self.settings = settings
        return self.settings

    def get_ingest_password_hash(self) -> str | None:
        return self.password_hash

    def update_ingest_password(
        self, *, rotated_at: datetime, updated_by: str, password_hash: str
    ) -> Settings:
        self.password_hash = password_hash
        password_status = replace(
            self.settings.dslr_password,
            is_set=True,
            updated_at=rotated_at,
            updated_by=updated_by,
        )
        self.settings = replace(self.settings, dslr_password=password_status)
        return self.settings


class DefaultSettingsService(SettingsService):
    """In-memory settings backed by :class:`AppConfig`."""

    def __init__(self, settings: Settings, password_hash: str) -> None:
        repository = InMemorySettingsRepository(
            settings=settings, password_hash=password_hash
        )
        audit_logger = InMemoryAuditLogger()
        super().__init__(
            repository=repository,
            security_service=SecurityService(),
            audit_logger=audit_logger,
        )
        self._repository_impl = repository
        self.audit_records = audit_logger.records


@dataclass(slots=True)
class DefaultSlotService(SlotService):
    """Simple slot registry loaded at application startup."""

    slots: Dict[str, Slot]

    def list_slots(self) -> list[Slot]:  # type: ignore[override]
        return list(self.slots.values())

    def get_slot(self, slot_id: str) -> Slot:  # type: ignore[override]
        try:
            return self.slots[slot_id]
        except KeyError as exc:
            raise KeyError(slot_id) from exc


@dataclass(slots=True)
class DefaultStatsService(StatsService):
    """In-memory statistics aggregator for scaffolding and tests."""

    events: list[ProcessingLog] = field(default_factory=list)

    def collect_global_stats(
        self, *, since: datetime | None = None
    ) -> Mapping[str, int]:  # type: ignore[override]
        return {}

    def collect_slot_stats(
        self, slot: Slot, *, since: datetime | None = None
    ) -> Mapping[str, int]:  # type: ignore[override]
        return {}

    def record_processing_event(self, log: ProcessingLog) -> None:  # type: ignore[override]
        self.events.append(log)


@dataclass(slots=True)
class DefaultMediaService(MediaService):
    """Registers media metadata for stored payloads."""

    media_root: Path
    objects: Dict[UUID, MediaObject] = field(default_factory=dict)

    def register_media(
        self,
        *,
        path: str,
        mime: str,
        size_bytes: int,
        expires_at: datetime,
        job_id: UUID | None = None,
    ) -> MediaObject:  # type: ignore[override]
        media = MediaObject(
            id=uuid4(),
            path=path,
            public_url=f"/media/{path}",
            expires_at=expires_at,
            created_at=_utcnow(),
            job_id=job_id,
            mime=mime,
            size_bytes=size_bytes,
        )
        self.objects[media.id] = media
        return media

    def get_media_by_path(self, path: str) -> MediaObject | None:  # type: ignore[override]
        for media in self.objects.values():
            if media.path == path:
                return media
        return None

    def save_result_media(
        self,
        *,
        job_id: UUID,
        data: bytes,
        mime: str,
        finalized_at: datetime,
        retention_hours: int,
        suggested_name: str | None = None,
    ) -> tuple[MediaObject, str]:  # type: ignore[override]
        if retention_hours <= 0:
            raise ValueError("retention_hours must be positive")

        root = self.media_root.resolve()
        results_dir = root / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        filename = self._build_result_filename(
            job_id,
            mime=mime,
            suggested_name=suggested_name,
        )
        target_path = results_dir / filename
        target_path.parent.mkdir(parents=True, exist_ok=True)
        with target_path.open("wb") as handle:
            handle.write(data)

        size_bytes = len(data)
        checksum = hashlib.sha256(data).hexdigest()
        expires_at = calculate_result_expires_at(
            finalized_at, result_retention_hours=retention_hours
        )
        relative_path = target_path.relative_to(root).as_posix()

        media = self.register_media(
            path=relative_path,
            mime=mime,
            size_bytes=size_bytes,
            expires_at=expires_at,
            job_id=job_id,
        )
        return media, checksum

    def revoke_media(self, media: MediaObject) -> None:  # type: ignore[override]
        self.objects.pop(media.id, None)
        try:
            file_path = (self.media_root / media.path).resolve()
            file_path.unlink(missing_ok=True)
        except FileNotFoundError:  # pragma: no cover - defensive cleanup
            return

    def purge_expired_media(self, *, now: datetime) -> list[MediaObject]:  # type: ignore[override]
        expired: list[MediaObject] = []
        for media in list(self.objects.values()):
            if media.expires_at <= now:
                expired.append(media)
                self.revoke_media(media)
        return expired

    @staticmethod
    def _build_result_filename(
        job_id: UUID, *, mime: str | None, suggested_name: str | None = None
    ) -> str:
        if suggested_name:
            candidate = Path(suggested_name).suffix
            if candidate:
                return f"{job_id.hex}{candidate}"

        extension = mimetypes.guess_extension(mime or "") or ""
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        if not extension:
            extension = ".bin"
        return f"{job_id.hex}{extension}"


@dataclass(slots=True)
class DefaultJobService(JobService):
    """Creates jobs and enqueues them using :class:`PostgresJobQueue`."""

    queue: PostgresJobQueue
    jobs: Dict[UUID, Job] = field(default_factory=dict)
    result_retention_hours: int = 72

    def _persist_finalized_job(self, job: Job) -> Job:
        mark_finalized = getattr(self.queue, "mark_finalized", None)
        if callable(mark_finalized):
            persisted = mark_finalized(job)
            self.jobs[persisted.id] = persisted
            return persisted
        self.jobs[job.id] = job
        return job

    def create_job(  # type: ignore[override]
        self,
        slot: Slot,
        *,
        payload: MediaObject | None,
        settings: Settings,
        job_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> Job:
        created = created_at or _utcnow()
        identifier = job_id or uuid4()
        expires_at = calculate_job_expires_at(
            created,
            sync_response_timeout_sec=settings.ingest.sync_response_timeout_sec,
            public_link_ttl_sec=settings.media_cache.public_link_ttl_sec,
        )
        job = Job(
            id=identifier,
            slot_id=slot.id,
            status=JobStatus.PENDING,
            is_finalized=False,
            failure_reason=None,
            expires_at=expires_at,
            created_at=created,
            updated_at=created,
            payload_path=payload.path if payload else None,
        )
        if payload is not None:
            payload.job_id = identifier
        self.jobs[identifier] = job
        try:
            self.queue.enqueue(job)
        except QueueBusyError:
            self.jobs.pop(identifier, None)
            raise
        except QueueUnavailableError:
            self.jobs.pop(identifier, None)
            raise
        return job

    def get_job(self, job_id: UUID) -> Job | None:  # type: ignore[override]
        return self.jobs.get(job_id)

    def acquire_next_job(self, *, now: datetime) -> Job | None:  # type: ignore[override]
        job = self.queue.acquire_for_processing(now=now)
        if job is not None:
            self.jobs[job.id] = job
        return job

    def finalize_job(
        self,
        job: Job,
        *,
        finalized_at: datetime,
        result_media: MediaObject | None,
        inline_preview: str | None,
        result_checksum: str | None,
    ) -> Job:  # type: ignore[override]
        job.finalized_at = finalized_at
        job.updated_at = finalized_at
        job.is_finalized = True
        job.failure_reason = None
        job.result_inline_base64 = None

        retention_expires_at = calculate_result_expires_at(
            finalized_at, result_retention_hours=self.result_retention_hours
        )

        if result_media is not None:
            job.result_file_path = result_media.path
            job.result_mime_type = result_media.mime
            job.result_size_bytes = result_media.size_bytes
            job.result_checksum = result_checksum
            job.result_expires_at = result_media.expires_at or retention_expires_at
        else:
            job.result_file_path = None
            job.result_mime_type = None
            job.result_size_bytes = None
            job.result_checksum = None
            job.result_expires_at = retention_expires_at
        return self._persist_finalized_job(job)

    def fail_job(
        self,
        job: Job,
        *,
        failure_reason: JobFailureReason,
        occurred_at: datetime,
    ) -> Job:  # type: ignore[override]
        job.is_finalized = True
        job.failure_reason = failure_reason
        job.updated_at = occurred_at
        job.finalized_at = occurred_at
        job.result_inline_base64 = None
        job.result_file_path = None
        job.result_mime_type = None
        job.result_size_bytes = None
        job.result_checksum = None
        job.result_expires_at = None
        return self._persist_finalized_job(job)

    def append_processing_logs(self, job: Job, logs: Iterable[ProcessingLog]) -> None:  # type: ignore[override]
        self.queue.append_processing_logs(logs)

    def purge_expired_results(self, *, now: datetime) -> list[Job]:  # type: ignore[override]
        expired: list[Job] = []
        persist = getattr(self.queue, "mark_finalized", None)
        if persist is not None and not callable(persist):
            persist = None
        for job in list(self.jobs.values()):
            expires_at = job.result_expires_at
            if expires_at is None or expires_at > now:
                continue
            job.result_file_path = None
            job.result_mime_type = None
            job.result_size_bytes = None
            job.result_checksum = None
            job.result_expires_at = None
            job.updated_at = now
            if persist is None:
                self.jobs[job.id] = job
                expired.append(job)
                continue
            try:
                persisted = persist(job)
            except QueueUnavailableError:
                self.jobs[job.id] = job
                expired.append(job)
            else:
                self.jobs[persisted.id] = persisted
                expired.append(persisted)
        return expired

    def refresh_recent_results(self, slot: Slot, *, limit: int = 10) -> Slot:  # type: ignore[override]
        raise NotImplementedError

    def clear_inline_preview(self, job: Job) -> Job:  # type: ignore[override]
        job.result_inline_base64 = None
        job.result_mime_type = None
        job.result_size_bytes = None
        job.result_checksum = None
        job.updated_at = _utcnow()
        self.jobs[job.id] = job
        return job


def bootstrap_settings(config: AppConfig, *, password_hash: str) -> Settings:
    now = _utcnow()
    return Settings(
        dslr_password=SettingsDslrPasswordStatus(
            is_set=True,
            updated_at=now,
            updated_by="bootstrap",
        ),
        ingest=SettingsIngestConfig(
            sync_response_timeout_sec=config.t_sync_response_seconds,
            ingest_ttl_sec=config.t_sync_response_seconds,
        ),
        media_cache=MediaCacheSettings(
            processed_media_ttl_hours=72,
            public_link_ttl_sec=config.t_sync_response_seconds,
        ),
        provider_keys={},
    )


def bootstrap_slots(config: AppConfig) -> Mapping[str, Slot]:
    now = _utcnow()
    slot = Slot(
        id="slot-001",
        name="Default Slot",
        provider_id="gemini",
        operation_id="style_transfer",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    return {slot.id: slot}


__all__ = [
    "DefaultJobService",
    "DefaultMediaService",
    "DefaultSettingsService",
    "DefaultSlotService",
    "DefaultStatsService",
    "bootstrap_settings",
    "bootstrap_slots",
]
