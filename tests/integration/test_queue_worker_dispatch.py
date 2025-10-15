from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Deque, Iterable, Mapping
from uuid import UUID, uuid4

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
)
from src.app.services import JobService, MediaService, SettingsService, SlotService, StatsService
from src.app.workers.queue_worker import QueueWorker
from tests.mocks.providers import (
    MockGeminiProvider,
    MockProviderConfig,
    MockProviderScenario,
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

    def get_slot(self, slot_id: str) -> Slot:  # type: ignore[override]
        if slot_id != self._slot.id:
            raise KeyError(slot_id)
        return self._slot


class StubSettingsService(SettingsService):
    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def read_settings(self) -> Settings:  # type: ignore[override]
        return self._settings


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


class StubStatsService(StatsService):
    def __init__(self) -> None:
        self.events: list[ProcessingLog] = []

    def record_processing_event(self, log: ProcessingLog) -> None:  # type: ignore[override]
        self.events.append(log)


@dataclass
class StubJobService(JobService):
    result_retention_hours: int = 72
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
    ) -> Job:  # type: ignore[override]
        job.finalized_at = finalized_at
        job.updated_at = finalized_at
        job.is_finalized = True
        job.failure_reason = None
        job.result_inline_base64 = inline_preview
        if result_media is not None:
            job.result_file_path = result_media.path
            job.result_mime_type = result_media.mime
            job.result_size_bytes = result_media.size_bytes
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
        self.logs.extend(logs)


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
        media_cache=MediaCacheSettings(processed_media_ttl_hours=72, public_link_ttl_sec=60),
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
def media_service() -> StubMediaService:
    return StubMediaService()


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


def _make_worker(
    *,
    clock: Clock,
    job_service: StubJobService,
    slot_service: StubSlotService,
    media_service: StubMediaService,
    settings_service: StubSettingsService,
    stats_service: StubStatsService,
    provider: MockGeminiProvider,
) -> QueueWorker:
    return QueueWorker(
        job_service=job_service,
        slot_service=slot_service,
        media_service=media_service,
        settings_service=settings_service,
        stats_service=stats_service,
        provider_factories={"gemini": lambda *, config=None: provider},
        clock=clock.now,
        sleep=lambda seconds: clock.advance(seconds),
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

    worker.run_once(now=clock.now())

    assert job in job_service.finalized_jobs
    assert job.failure_reason is None
    assert job.result_inline_base64 == TRANSPARENT_PNG_BASE64
    assert job.result_expires_at == job.finalized_at + timedelta(hours=72)
    assert any(log.status is ProcessingStatus.SUCCEEDED for log in job_service.logs)
    assert stats_service.events
    assert provider_success.events[-1].startswith("poll:")


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

    worker.run_once(now=clock.now())

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

    worker.run_once(now=clock.now())

    assert job in job_service.failed_jobs
    assert job.failure_reason is JobFailureReason.PROVIDER_ERROR
    assert any(log.status is ProcessingStatus.FAILED for log in job_service.logs)
    assert provider_error.events.count("submit:attempt") == 1
