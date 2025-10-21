from __future__ import annotations

import asyncio
import json
import mimetypes
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Iterable
from uuid import UUID, uuid4

import base64
import hashlib
import pytest

from src.app.domain import deadlines
from src.app.domain.models import (
    Job,
    JobFailureReason,
    JobStatus,
    MediaCacheSettings,
    MediaObject,
    ProcessingLog,
    ProcessingStatus,
    Settings,
    SettingsDslrPasswordStatus,
    SettingsIngestConfig,
    SettingsProviderKeyStatus,
    Slot,
    TemplateMedia,
)
from src.app.providers.base import ProviderAdapter
from src.app.services import (
    JobService,
    MediaService,
    SlotService,
    StatsService,
)
from src.app.services.default import DefaultSettingsService
from src.app.workers.queue_worker import QueueWorker
from tests.mocks.providers import (
    MockGeminiProvider,
    MockProviderConfig,
    MockProviderScenario,
    MockTurbotextProvider,
    TRANSPARENT_PNG_BASE64,
)


class Clock:
    """Deterministic clock used to control worker timing in tests."""

    def __init__(self, start: datetime) -> None:
        self._current = start

    def now(self) -> datetime:
        return self._current

    def advance(self, seconds: float) -> datetime:
        self._current += timedelta(seconds=seconds)
        return self._current


class StubSlotService(SlotService):
    def __init__(self, slot: Slot) -> None:
        self._slot = slot

    async def list_slots(
        self, *, include_archived: bool = False
    ) -> list[Slot]:  # type: ignore[override]
        _ = include_archived
        return [self._slot]

    async def get_slot(
        self, slot_id: str, *, include_templates: bool = True
    ) -> Slot:  # type: ignore[override]
        _ = include_templates
        if slot_id != self._slot.id:
            raise KeyError(slot_id)
        return self._slot

    async def create_slot(
        self, slot: Slot, *, updated_by: str | None = None
    ) -> Slot:  # type: ignore[override]
        _ = updated_by
        self._slot = slot
        return slot

    async def update_slot(
        self,
        slot: Slot,
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:  # type: ignore[override]
        _ = (expected_etag, updated_by)
        self._slot = slot
        return slot

    async def archive_slot(
        self, slot_id: str, *, expected_etag: str, updated_by: str | None = None
    ) -> Slot:  # type: ignore[override]
        _ = (expected_etag, updated_by)
        if slot_id != self._slot.id:
            raise KeyError(slot_id)
        return self._slot

    async def attach_templates(
        self,
        slot_id: str,
        templates: Iterable[TemplateMedia],
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:  # type: ignore[override]
        _ = (slot_id, templates, expected_etag, updated_by)
        return self._slot

    async def detach_template(
        self,
        slot_id: str,
        template_id: UUID,
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:  # type: ignore[override]
        _ = (slot_id, template_id, expected_etag, updated_by)
        return self._slot


class StubSettingsService(DefaultSettingsService):
    def __init__(self, settings: Settings) -> None:
        super().__init__(settings=settings, password_hash="")

    def verify_ingest_password(self, password: str) -> bool:  # type: ignore[override]
        return True


class StubMediaService(MediaService):
    def __init__(self) -> None:
        self.registered: list[MediaObject] = []

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
            public_url=path,
            expires_at=expires_at,
            created_at=expires_at,
            job_id=job_id,
            mime=mime,
            size_bytes=size_bytes,
        )
        self.registered.append(media)
        return media

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
        media_root = Path(getattr(self, "media_root", Path("."))).resolve()
        results_dir = media_root / "results"
        results_dir.mkdir(parents=True, exist_ok=True)

        filename = self._build_result_filename(
            job_id,
            mime=mime,
            suggested_name=suggested_name,
        )
        target = results_dir / filename
        target.write_bytes(data)

        expires_at = deadlines.calculate_result_expires_at(
            finalized_at,
            result_retention_hours=retention_hours,
        )
        relative_path = target.relative_to(media_root).as_posix()
        media = self.register_media(
            path=relative_path,
            mime=mime,
            size_bytes=len(data),
            expires_at=expires_at,
            job_id=job_id,
        )
        checksum = hashlib.sha256(data).hexdigest()
        return media, checksum

    @staticmethod
    def _build_result_filename(
        job_id: UUID, *, mime: str | None, suggested_name: str | None = None
    ) -> str:
        if suggested_name:
            suffix = Path(suggested_name).suffix
            if suffix:
                return f"{job_id.hex}{suffix}"

        extension = mimetypes.guess_extension(mime or "") or ""
        if extension and not extension.startswith("."):
            extension = f".{extension}"
        if not extension:
            extension = ".bin"
        return f"{job_id.hex}{extension}"


class StubStatsService(StatsService):
    def __init__(self) -> None:
        self.events: list[ProcessingLog] = []

    def record_processing_event(self, log: ProcessingLog) -> None:  # type: ignore[override]
        self.events.append(log)


@dataclass
class StubJobService(JobService):
    result_retention_hours: int = 72
    stats_service: StatsService | None = None
    _queue: Deque[Job] = field(default_factory=deque)
    finalized_jobs: list[Job] = field(default_factory=list)
    failed_jobs: list[Job] = field(default_factory=list)
    logs: list[ProcessingLog] = field(default_factory=list)

    def queue(self, job: Job) -> None:
        self._queue.append(job)

    def acquire_next_job(self, *, now: datetime) -> Job | None:  # type: ignore[override]
        if not self._queue:
            return None
        job = self._queue.popleft()
        job.status = JobStatus.PROCESSING
        job.updated_at = now
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
        if result_media is not None:
            job.result_file_path = result_media.path
            job.result_mime_type = result_media.mime
            job.result_size_bytes = result_media.size_bytes
            job.result_checksum = result_checksum
        else:
            job.result_file_path = None
            job.result_mime_type = None
            job.result_size_bytes = None
            job.result_checksum = None
        job.result_expires_at = deadlines.calculate_result_expires_at(
            finalized_at,
            result_retention_hours=self.result_retention_hours,
        )
        self.finalized_jobs.append(job)
        return job

    def fail_job(
        self,
        job: Job,
        *,
        failure_reason: JobFailureReason,
        occurred_at: datetime,
    ) -> Job:  # type: ignore[override]
        job.finalized_at = occurred_at
        job.updated_at = occurred_at
        job.is_finalized = True
        job.failure_reason = failure_reason
        job.result_inline_base64 = None
        job.result_file_path = None
        job.result_mime_type = None
        job.result_size_bytes = None
        job.result_checksum = None
        job.result_expires_at = None
        self.failed_jobs.append(job)
        return job

    def append_processing_logs(
        self, job: Job, logs: Iterable[ProcessingLog]
    ) -> None:  # type: ignore[override]
        _ = job
        materialized = list(logs)
        self.logs.extend(materialized)
        if self.stats_service is not None:
            for log in materialized:
                self.stats_service.record_processing_event(log)


@pytest.fixture
def clock() -> Clock:
    return Clock(datetime(2025, 10, 18, 12, 0, tzinfo=timezone.utc))


@pytest.fixture
def slot(clock: Clock) -> Slot:
    now = clock.now()
    return Slot(
        id="slot-queue-worker",
        name="Queue Worker Slot",
        provider_id="gemini",
        operation_id="models.generateContent",
        settings_json={},
        created_at=now,
        updated_at=now,
    )


@pytest.fixture
def settings() -> Settings:
    return Settings(
        dslr_password=SettingsDslrPasswordStatus(is_set=False),
        ingest=SettingsIngestConfig(sync_response_timeout_sec=180, ingest_ttl_sec=180),
        media_cache=MediaCacheSettings(
            processed_media_ttl_hours=72, public_link_ttl_sec=60
        ),
        provider_keys={
            "gemini": SettingsProviderKeyStatus(
                is_configured=True,
                updated_at=None,
                updated_by=None,
                extra={"project_id": "mock-project"},
            )
        },
    )


@pytest.fixture
def job(clock: Clock, tmp_path: Path) -> Job:
    created = clock.now()
    payload_path = tmp_path / "payload.json"
    payload_path.write_text(
        json.dumps({"provider_context": {"prompt": "Render portrait"}}),
        encoding="utf-8",
    )
    return Job(
        id=uuid4(),
        slot_id="slot-queue-worker",
        status=JobStatus.PENDING,
        is_finalized=False,
        failure_reason=None,
        expires_at=created + timedelta(seconds=120),
        created_at=created,
        updated_at=created,
        finalized_at=None,
        payload_path=str(payload_path),
    )


@pytest.fixture
def job_service() -> StubJobService:
    return StubJobService()


@pytest.fixture
def slot_service(slot: Slot) -> StubSlotService:
    return StubSlotService(slot)


@pytest.fixture
def settings_service(settings: Settings) -> StubSettingsService:
    return StubSettingsService(settings)


@pytest.fixture
def media_root(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    root = tmp_path / "media"
    monkeypatch.setenv("PHOTOCHANGER_MEDIA_ROOT", str(root))
    return root


@pytest.fixture
def media_service(media_root: Path) -> StubMediaService:
    service = StubMediaService()
    service.media_root = media_root
    return service


@pytest.fixture
def stats_service() -> StubStatsService:
    return StubStatsService()


@pytest.fixture
def provider_success() -> MockGeminiProvider:
    config = MockProviderConfig(
        scenario=MockProviderScenario.SUCCESS,
        timeout_polls=1,
    )
    return MockGeminiProvider(config)


@pytest.fixture
def provider_timeout() -> MockGeminiProvider:
    config = MockProviderConfig(
        scenario=MockProviderScenario.TIMEOUT,
        timeout_polls=1,
    )
    return MockGeminiProvider(config)


@pytest.fixture
def provider_error() -> MockGeminiProvider:
    config = MockProviderConfig(
        scenario=MockProviderScenario.ERROR,
    )
    return MockGeminiProvider(config)


@pytest.fixture
def provider_turbotext() -> MockTurbotextProvider:
    config = MockProviderConfig(
        scenario=MockProviderScenario.SUCCESS,
        timeout_polls=1,
    )
    return MockTurbotextProvider(config)


def _make_worker(
    *,
    clock: Clock,
    job_service: StubJobService,
    slot_service: StubSlotService,
    media_service: StubMediaService,
    settings_service: StubSettingsService,
    stats_service: StubStatsService,
    provider: ProviderAdapter,
    provider_id: str = "gemini",
) -> QueueWorker:
    async def _advance(seconds: float) -> None:
        clock.advance(seconds)

    job_service.stats_service = stats_service
    return QueueWorker(
        job_service=job_service,
        slot_service=slot_service,
        media_service=media_service,
        settings_service=settings_service,
        provider_factories={provider_id: lambda *, config=None: provider},
        clock=clock.now,
        sleep=_advance,
        poll_interval=1.0,
        max_poll_attempts=4,
    )


@pytest.mark.integration
def test_worker_finalizes_successful_job(
    clock: Clock,
    job_service: StubJobService,
    slot_service: StubSlotService,
    media_service: StubMediaService,
    settings_service: StubSettingsService,
    stats_service: StubStatsService,
    provider_success: MockGeminiProvider,
    job: Job,
    media_root: Path,
) -> None:
    worker = _make_worker(
        clock=clock,
        job_service=job_service,
        slot_service=slot_service,
        media_service=media_service,
        settings_service=settings_service,
        stats_service=stats_service,
        provider=provider_success,
    )
    job_service.queue(job)

    asyncio.run(worker.run_once(now=clock.now()))

    assert job in job_service.finalized_jobs
    assert job.failure_reason is None
    assert job.result_inline_base64 is None
    assert job.result_expires_at == job.finalized_at + timedelta(hours=72)
    assert any(log.status is ProcessingStatus.SUCCEEDED for log in job_service.logs)
    assert stats_service.events
    assert provider_success.events[-1].startswith("poll:")

    decoded = base64.b64decode(TRANSPARENT_PNG_BASE64)
    expected_checksum = hashlib.sha256(decoded).hexdigest()
    assert job.result_file_path is not None
    assert job.result_mime_type == "image/png"
    assert job.result_size_bytes == len(decoded)
    assert job.result_checksum == expected_checksum
    assert media_service.registered
    assert media_service.registered[0].path == job.result_file_path

    result_path = media_root / job.result_file_path
    assert result_path.exists()
    assert result_path.read_bytes() == decoded


@pytest.mark.integration
def test_worker_marks_timeout_and_cancels_provider(
    clock: Clock,
    job_service: StubJobService,
    slot_service: StubSlotService,
    media_service: StubMediaService,
    settings_service: StubSettingsService,
    stats_service: StubStatsService,
    provider_timeout: MockGeminiProvider,
    job: Job,
) -> None:
    worker = _make_worker(
        clock=clock,
        job_service=job_service,
        slot_service=slot_service,
        media_service=media_service,
        settings_service=settings_service,
        stats_service=stats_service,
        provider=provider_timeout,
    )
    job.expires_at = clock.now() + timedelta(seconds=2)
    job_service.queue(job)

    asyncio.run(worker.run_once(now=clock.now()))

    assert job in job_service.failed_jobs
    assert job.failure_reason is JobFailureReason.TIMEOUT
    assert any(log.status is ProcessingStatus.TIMEOUT for log in job_service.logs)
    assert any(event.startswith("cancel:") for event in provider_timeout.events)


@pytest.mark.integration
def test_worker_handles_provider_error(
    clock: Clock,
    job_service: StubJobService,
    slot_service: StubSlotService,
    media_service: StubMediaService,
    settings_service: StubSettingsService,
    stats_service: StubStatsService,
    provider_error: MockGeminiProvider,
    job: Job,
) -> None:
    worker = _make_worker(
        clock=clock,
        job_service=job_service,
        slot_service=slot_service,
        media_service=media_service,
        settings_service=settings_service,
        stats_service=stats_service,
        provider=provider_error,
    )
    job_service.queue(job)

    asyncio.run(worker.run_once(now=clock.now()))

    assert job in job_service.failed_jobs
    assert job.failure_reason is JobFailureReason.PROVIDER_ERROR
    assert any(log.status is ProcessingStatus.FAILED for log in job_service.logs)
    assert provider_error.events.count("submit:attempt") == 1


@pytest.mark.integration
def test_worker_materializes_turbotext_result(
    clock: Clock,
    job_service: StubJobService,
    media_service: StubMediaService,
    settings_service: StubSettingsService,
    stats_service: StubStatsService,
    provider_turbotext: MockTurbotextProvider,
    media_root: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    now = clock.now()
    slot = Slot(
        id="slot-turbotext",
        name="Turbotext Slot",
        provider_id="turbotext",
        operation_id="generate_image2image",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    slot_service = StubSlotService(slot)
    job = Job(
        id=uuid4(),
        slot_id=slot.id,
        status=JobStatus.PENDING,
        is_finalized=False,
        failure_reason=None,
        expires_at=now + timedelta(seconds=120),
        created_at=now,
        updated_at=now,
        finalized_at=None,
    )

    async def _fake_fetch(
        self: QueueWorker, url: str
    ) -> tuple[bytes, str | None, str | None]:
        _ = url
        return b"turbotext-bytes", "image/png", "turbotext.png"

    monkeypatch.setattr(QueueWorker, "_fetch_uploaded_image", _fake_fetch)

    worker = _make_worker(
        clock=clock,
        job_service=job_service,
        slot_service=slot_service,
        media_service=media_service,
        settings_service=settings_service,
        stats_service=stats_service,
        provider=provider_turbotext,
        provider_id="turbotext",
    )
    job_service.queue(job)

    asyncio.run(worker.run_once(now=clock.now()))

    assert job in job_service.finalized_jobs
    assert job.failure_reason is None
    assert job.result_inline_base64 is None
    assert job.result_file_path is not None
    assert job.result_mime_type == "image/png"
    assert job.result_size_bytes == len(b"turbotext-bytes")
    expected_checksum = hashlib.sha256(b"turbotext-bytes").hexdigest()
    assert job.result_checksum == expected_checksum
    assert job.result_expires_at == job.finalized_at + timedelta(hours=72)
    assert media_service.registered
    assert media_service.registered[0].path == job.result_file_path

    result_path = media_root / job.result_file_path
    assert result_path.exists()
    assert result_path.read_bytes() == b"turbotext-bytes"
    assert any(event.startswith("poll:") for event in provider_turbotext.events)
