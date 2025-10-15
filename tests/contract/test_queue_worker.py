"""Integration-style contract tests for the queue worker scaffolding.

The real PostgreSQL queue and worker implementations are not available in
phase 3, therefore the tests provide lightweight doubles that mimic the
behaviour described in ``spec/docs/blueprints/domain-model.md``:

* :class:`InMemoryQueueDouble` reproduces ``enqueue``/``acquire``/``mark``
  semantics and keeps jobs in memory while respecting ``expires_at``.
* :class:`InMemoryJobService` performs finalisation/timeout bookkeeping and
  delegates deadline arithmetic to patched helpers from
  :mod:`src.app.domain.deadlines`.
* :class:`InstrumentedWorker` exercises the control flow between the queue,
  job service and mocked provider adapter, enabling us to verify end-to-end
  contract expectations without hitting the database.

Each test is marked both as ``contract`` and ``integration`` to align with the
pytest marker policy outlined in ``tests/HOWTO.md``.
"""

from __future__ import annotations

import asyncio
from collections import deque
from datetime import datetime, timedelta, timezone
from typing import Deque, Dict, Iterable, Iterator
from uuid import UUID, uuid4

import pytest
from unittest.mock import AsyncMock, Mock, create_autospec

from src.app.domain import deadlines
from src.app.domain.models import Job, JobFailureReason, JobStatus, MediaObject
from src.app.infrastructure.queue.postgres import PostgresJobQueue, PostgresQueueConfig
from src.app.providers.base import ProviderAdapter
from src.app.services.job_service import JobService
from src.app.workers.queue_worker import QueueWorker


class TimeController:
    """Mutable clock helper so tests can fast-forward ``now`` deterministically."""

    def __init__(self, *, start: datetime) -> None:
        self._current = start

    @property
    def now(self) -> datetime:
        return self._current

    def advance(self, *, seconds: int = 0) -> datetime:
        self._current += timedelta(seconds=seconds)
        return self._current


class InMemoryQueueDouble(PostgresJobQueue):
    """In-memory replacement for ``PostgresJobQueue`` used in integration tests."""

    def __init__(self) -> None:
        super().__init__(config=PostgresQueueConfig(dsn="postgresql://contract-tests"))
        self._pending: Deque[UUID] = deque()
        self._jobs: Dict[UUID, Job] = {}

    def enqueue(self, job: Job) -> Job:  # type: ignore[override]
        if job.id not in self._jobs:
            self._pending.append(job.id)
        job.status = JobStatus.PENDING
        job.is_finalized = False
        job.failure_reason = None
        self._jobs[job.id] = job
        return job

    def acquire_for_processing(self, *, now: datetime) -> Job | None:  # type: ignore[override]
        for job_id in list(self._pending):
            job = self._jobs[job_id]
            if job.is_finalized:
                self._pending.remove(job_id)
                continue
            if job.expires_at <= now:
                # Expired jobs are handled separately via ``release_expired``.
                continue
            self._pending.remove(job_id)
            job.status = JobStatus.PROCESSING
            job.updated_at = now
            return job
        return None

    def mark_finalized(self, job: Job) -> Job:  # type: ignore[override]
        if job.id in self._pending:
            self._pending.remove(job.id)
        self._jobs[job.id] = job
        return job

    def release_expired(self, *, now: datetime) -> Iterable[Job]:  # type: ignore[override]
        return [
            job
            for job in self._jobs.values()
            if not job.is_finalized and job.expires_at <= now
        ]


class InMemoryJobService(JobService):
    """Job service double that updates :class:`Job` records synchronously."""

    def __init__(self, queue: InMemoryQueueDouble, *, result_retention_hours: int) -> None:
        self._queue = queue
        self._result_retention_hours = result_retention_hours
        self.finalized_jobs: list[Job] = []
        self.failed_jobs: list[Job] = []

    def acquire_next_job(self, *, now: datetime) -> Job | None:  # type: ignore[override]
        return self._queue.acquire_for_processing(now=now)

    def finalize_job(  # type: ignore[override]
        self,
        job: Job,
        *,
        finalized_at: datetime,
        result_media: MediaObject | None,
        inline_preview: str | None,
    ) -> Job:
        job.finalized_at = finalized_at
        job.updated_at = finalized_at
        job.is_finalized = True
        job.failure_reason = None
        if result_media is not None:
            job.result_file_path = result_media.path
            job.result_mime_type = result_media.mime
            job.result_size_bytes = result_media.size_bytes
            job.result_checksum = "mock-checksum"
        job.result_inline_base64 = None  # Cleared after synchronous HTTP delivery.
        job.result_expires_at = deadlines.calculate_result_expires_at(
            finalized_at,
            result_retention_hours=self._result_retention_hours,
        )
        self._queue.mark_finalized(job)
        self.finalized_jobs.append(job)
        return job

    def fail_job(  # type: ignore[override]
        self,
        job: Job,
        *,
        failure_reason: JobFailureReason,
        occurred_at: datetime,
    ) -> Job:
        job.finalized_at = occurred_at
        job.updated_at = occurred_at
        job.is_finalized = True
        job.failure_reason = failure_reason
        job.result_file_path = None
        job.result_inline_base64 = None
        job.result_mime_type = None
        job.result_size_bytes = None
        job.result_checksum = None
        job.result_expires_at = None
        self._queue.mark_finalized(job)
        self.failed_jobs.append(job)
        return job


class InstrumentedWorker(QueueWorker):
    """Minimal worker that finalises jobs immediately for integration tests."""

    def __init__(
        self,
        *,
        job_service: InMemoryJobService,
        media_service: Mock,
        settings_service: Mock,
        stats_service: Mock,
        provider: ProviderAdapter,
    ) -> None:
        super().__init__(
            job_service=job_service,
            media_service=media_service,
            settings_service=settings_service,
            stats_service=stats_service,
        )
        self.provider = provider

    def run_once(self, *, now: datetime) -> None:  # type: ignore[override]
        job = self.job_service.acquire_next_job(now=now)
        if job is None:
            return
        if now >= job.expires_at:
            self.handle_timeout(job, now=now)
            return
        self.process_job(job, now=now)

    def process_job(self, job: Job, *, now: datetime) -> None:  # type: ignore[override]
        preview = "cHJldmlldy1iaW5hcnk="
        job.provider_job_reference = f"provider-{job.id.hex}"
        job.result_inline_base64 = preview
        media = MediaObject(
            id=uuid4(),
            path=f"results/{job.id.hex}.png",
            public_url=f"https://cdn.test/{job.id.hex}.png",
            expires_at=now + timedelta(hours=72),
            created_at=now,
            job_id=job.id,
            mime="image/png",
            size_bytes=4096,
        )
        self.job_service.finalize_job(
            job,
            finalized_at=now,
            result_media=media,
            inline_preview=preview,
        )

    def handle_timeout(self, job: Job, *, now: datetime) -> None:  # type: ignore[override]
        self.job_service.fail_job(
            job,
            failure_reason=JobFailureReason.TIMEOUT,
            occurred_at=now,
        )

    def cancel_job(self, job: Job, *, now: datetime) -> None:
        if job.provider_job_reference is not None:
            asyncio.run(self.provider.cancel(job.provider_job_reference))
        self.job_service.fail_job(
            job,
            failure_reason=JobFailureReason.CANCELLED,
            occurred_at=now,
        )


@pytest.fixture(autouse=True)
def patch_deadline_helpers(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
    """Replace TTL helpers with arithmetic suitable for deterministic tests."""

    def _job_expires_at(
        created_at: datetime,
        *,
        sync_response_timeout_sec: int,
        public_link_ttl_sec: int,
    ) -> datetime:
        assert sync_response_timeout_sec == public_link_ttl_sec
        return created_at + timedelta(seconds=sync_response_timeout_sec)

    def _result_expires_at(
        finalized_at: datetime, *, result_retention_hours: int
    ) -> datetime:
        return finalized_at + timedelta(hours=result_retention_hours)

    monkeypatch.setattr(deadlines, "calculate_job_expires_at", _job_expires_at)
    monkeypatch.setattr(deadlines, "calculate_result_expires_at", _result_expires_at)
    yield


@pytest.fixture
def time_controller() -> TimeController:
    return TimeController(start=datetime(2025, 10, 18, 12, 0, tzinfo=timezone.utc))


@pytest.fixture
def queue_double() -> InMemoryQueueDouble:
    return InMemoryQueueDouble()


@pytest.fixture
def job_service(queue_double: InMemoryQueueDouble) -> InMemoryJobService:
    return InMemoryJobService(queue_double, result_retention_hours=72)


@pytest.fixture
def provider() -> ProviderAdapter:
    provider_mock = create_autospec(ProviderAdapter, instance=True)
    provider_mock.cancel = AsyncMock(name="cancel")
    provider_mock.provider_id = "mock-provider"
    return provider_mock


@pytest.fixture
def worker(job_service: InMemoryJobService, provider: ProviderAdapter) -> InstrumentedWorker:
    return InstrumentedWorker(
        job_service=job_service,
        media_service=Mock(name="media_service"),
        settings_service=Mock(name="settings_service"),
        stats_service=Mock(name="stats_service"),
        provider=provider,
    )


@pytest.fixture
def make_job(time_controller: TimeController):
    def _factory(
        *,
        slot_id: str = "slot-001",
        sync_timeout_sec: int = 120,
        payload_path: str | None = None,
        result_file_path: str | None = None,
        result_inline_base64: str | None = None,
    ) -> Job:
        created_at = time_controller.now
        expires_at = deadlines.calculate_job_expires_at(
            created_at,
            sync_response_timeout_sec=sync_timeout_sec,
            public_link_ttl_sec=sync_timeout_sec,
        )
        return Job(
            id=uuid4(),
            slot_id=slot_id,
            status=JobStatus.PENDING,
            is_finalized=False,
            failure_reason=None,
            expires_at=expires_at,
            created_at=created_at,
            updated_at=created_at,
            finalized_at=None,
            payload_path=payload_path or f"payloads/{slot_id}.json",
            provider_job_reference=None,
            result_file_path=result_file_path,
            result_inline_base64=result_inline_base64,
            result_mime_type=None,
            result_size_bytes=None,
            result_checksum=None,
            result_expires_at=None,
        )

    return _factory


@pytest.mark.contract
@pytest.mark.integration
def test_worker_finalizes_job_within_sync_window(
    queue_double: InMemoryQueueDouble,
    worker: InstrumentedWorker,
    job_service: InMemoryJobService,
    make_job,
    time_controller: TimeController,
) -> None:
    """Full cycle: enqueue → acquire → finalize within ``T_sync_response``."""

    job = make_job(sync_timeout_sec=180)
    queue_double.enqueue(job)

    processing_time = time_controller.advance(seconds=90)
    assert processing_time < job.expires_at

    worker.run_once(now=processing_time)

    assert job.is_finalized is True
    assert job.failure_reason is None
    assert job.finalized_at == processing_time
    assert job.result_file_path == f"results/{job.id.hex}.png"
    assert job.result_mime_type == "image/png"
    assert job.result_inline_base64 is None
    assert job.result_expires_at == processing_time + timedelta(hours=72)
    assert job_service.finalized_jobs == [job]


@pytest.mark.contract
@pytest.mark.integration
def test_manual_cancel_invokes_provider_and_marks_failure(
    queue_double: InMemoryQueueDouble,
    worker: InstrumentedWorker,
    provider: ProviderAdapter,
    job_service: InMemoryJobService,
    make_job,
    time_controller: TimeController,
) -> None:
    """Manual cancellation calls ``ProviderAdapter.cancel`` and flags the job."""

    job = make_job()
    job.provider_job_reference = "provider-001"
    queue_double.enqueue(job)

    cancel_at = time_controller.advance(seconds=10)
    worker.cancel_job(job, now=cancel_at)

    provider.cancel.assert_awaited_once_with("provider-001")
    assert job.is_finalized is True
    assert job.failure_reason == JobFailureReason.CANCELLED
    assert job.finalized_at == cancel_at
    assert job.result_file_path is None
    assert job.result_inline_base64 is None
    assert job_service.failed_jobs == [job]


@pytest.mark.contract
@pytest.mark.integration
def test_release_expired_jobs_trigger_timeout_processing(
    queue_double: InMemoryQueueDouble,
    worker: InstrumentedWorker,
    job_service: InMemoryJobService,
    make_job,
    time_controller: TimeController,
) -> None:
    """Expired jobs are released for timeout handling and cleaned up."""

    job = make_job(sync_timeout_sec=30, result_file_path="results/pending.bin", result_inline_base64="cHJldmlldyI=")
    queue_double.enqueue(job)

    expired_now = time_controller.advance(seconds=45)
    assert expired_now > job.expires_at

    expired_jobs = list(queue_double.release_expired(now=expired_now))
    assert expired_jobs == [job]

    worker.handle_timeout(job, now=expired_now)

    assert job.is_finalized is True
    assert job.failure_reason == JobFailureReason.TIMEOUT
    assert job.result_file_path is None
    assert job.result_inline_base64 is None
    assert job_service.failed_jobs == [job]
