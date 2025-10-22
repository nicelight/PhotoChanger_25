"""Integration-style contract tests for the queue worker scaffolding.

The suite now relies on the real PostgreSQL-backed queue and
:class:`~src.app.services.default.DefaultJobService` to verify end-to-end
behaviour. A lightweight :class:`InstrumentedWorker` is still used to avoid
touching provider adapters, but all queue interactions go through the live
database provided by the ``postgres_queue`` fixture.

Each test is marked both as ``contract`` and ``integration`` to align with the
pytest marker policy outlined in ``tests/HOWTO.md``.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Iterator
from uuid import UUID, uuid4

import pytest
from unittest.mock import Mock

from src.app.domain import deadlines
from src.app.domain.models import Job, JobFailureReason, JobStatus, MediaObject, Slot
from src.app.infrastructure.queue.postgres import PostgresJobQueue
from src.app.services.default import DefaultJobService
from src.app.providers.base import ProviderAdapter
from src.app.workers.queue_worker import QueueWorker

from tests.mocks.providers import (
    MockGeminiProvider,
    MockProviderConfig,
    MockProviderScenario,
)


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


class InstrumentedWorker(QueueWorker):
    """Minimal worker that finalises jobs immediately for integration tests."""

    def __init__(
        self,
        *,
        job_service: DefaultJobService,
        media_service: Mock,
        settings_service: Mock,
        provider: ProviderAdapter,
    ) -> None:
        super().__init__(
            job_service=job_service,
            slot_service=Mock(name="slot_service"),
            media_service=media_service,
            settings_service=settings_service,
            provider_factories={},
        )
        self.provider = provider

    async def run_once(
        self, *, now: datetime, shutdown_event: asyncio.Event | None = None
    ) -> bool:  # type: ignore[override]
        job = self.job_service.acquire_next_job(now=now)
        if job is None:
            return False
        if now >= job.expires_at:
            await self.handle_timeout(job, now=now)
            return True
        await self.process_job(job, now=now, shutdown_event=shutdown_event)
        return True

    async def process_job(
        self, job: Job, *, now: datetime, shutdown_event: asyncio.Event | None = None
    ) -> None:  # type: ignore[override]
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
        persisted = self.job_service.finalize_job(
            job,
            finalized_at=now,
            result_media=media,
            inline_preview=preview,
            result_checksum="sha256:deadbeef",
        )
        self.job_service.jobs[job.id] = persisted

    async def handle_timeout(  # type: ignore[override]
        self, job: Job, *, now: datetime
    ) -> None:
        job.result_file_path = None
        job.result_inline_base64 = None
        failed = self.job_service.fail_job(
            job,
            failure_reason=JobFailureReason.TIMEOUT,
            occurred_at=now,
        )
        self.job_service.jobs[job.id] = failed

    async def cancel_job(self, job: Job, *, now: datetime) -> None:
        if job.provider_job_reference is not None:
            await self.provider.cancel(job.provider_job_reference)
        job.result_file_path = None
        job.result_inline_base64 = None
        failed = self.job_service.fail_job(
            job,
            failure_reason=JobFailureReason.CANCELLED,
            occurred_at=now,
        )
        self.job_service.jobs[job.id] = failed


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
    from src.app.services import default as default_services

    monkeypatch.setattr(
        default_services, "calculate_job_expires_at", _job_expires_at
    )
    monkeypatch.setattr(
        default_services, "calculate_result_expires_at", _result_expires_at
    )
    yield


@pytest.fixture
def time_controller() -> TimeController:
    return TimeController(start=datetime(2025, 10, 18, 12, 0, tzinfo=timezone.utc))


@pytest.fixture
def job_service(postgres_queue: PostgresJobQueue) -> DefaultJobService:
    service = DefaultJobService(queue=postgres_queue)
    service.result_retention_hours = 72
    return service


@pytest.fixture
def provider() -> MockGeminiProvider:
    config = MockProviderConfig(
        scenario=MockProviderScenario.SUCCESS,
        timeout_polls=2,
        error_code="RESOURCE_EXHAUSTED",
        error_message="Quota exceeded for mock Gemini project",
    )
    return MockGeminiProvider(config)


@pytest.fixture
def worker(
    job_service: DefaultJobService, provider: ProviderAdapter
) -> InstrumentedWorker:
    return InstrumentedWorker(
        job_service=job_service,
        media_service=Mock(name="media_service"),
        settings_service=Mock(name="settings_service"),
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


@pytest.fixture
def slot(time_controller: TimeController) -> Slot:
    now = time_controller.now
    return Slot(
        id="slot-001",
        name="Primary Slot",
        provider_id="gemini",
        operation_id="models.generateContent",
        settings_json={},
        created_at=now,
        updated_at=now,
    )


@pytest.mark.contract
@pytest.mark.integration
def test_worker_finalizes_job_within_sync_window(
    postgres_queue: PostgresJobQueue,
    worker: InstrumentedWorker,
    job_service: DefaultJobService,
    make_job,
    time_controller: TimeController,
) -> None:
    """Full cycle: enqueue → acquire → finalize within ``T_sync_response``."""

    job = make_job(sync_timeout_sec=180)
    postgres_queue.enqueue(job)

    processing_time = time_controller.advance(seconds=90)
    assert processing_time < job.expires_at

    asyncio.run(worker.run_once(now=processing_time))

    persisted = job_service.get_job(job.id)
    assert persisted is not None
    assert persisted.is_finalized is True
    assert persisted.failure_reason is None
    assert persisted.finalized_at == processing_time
    assert persisted.result_file_path == f"results/{job.id.hex}.png"
    assert persisted.result_mime_type == "image/png"
    assert persisted.result_inline_base64 is None
    assert persisted.result_checksum == "sha256:deadbeef"
    assert persisted.result_expires_at == processing_time + timedelta(hours=72)


@pytest.mark.contract
@pytest.mark.integration
def test_manual_cancel_invokes_provider_and_marks_failure(
    postgres_queue: PostgresJobQueue,
    worker: InstrumentedWorker,
    provider: MockGeminiProvider,
    job_service: DefaultJobService,
    make_job,
    time_controller: TimeController,
    slot: Slot,
) -> None:
    """Manual cancellation calls ``ProviderAdapter.cancel`` and flags the job."""

    job = make_job()
    payload = provider.prepare_payload(
        job=job,
        slot=slot,
        settings={},
        context={"prompt": "Cancel scenario"},
    )
    reference = asyncio.run(provider.submit_job(payload))
    job.provider_job_reference = reference
    postgres_queue.enqueue(job)

    cancel_at = time_controller.advance(seconds=10)
    asyncio.run(worker.cancel_job(job, now=cancel_at))

    assert provider.events[-1] == f"cancel:{reference}"
    with pytest.raises(RuntimeError, match="cancelled"):
        asyncio.run(provider.poll_status(reference))
    persisted = job_service.get_job(job.id)
    assert persisted is not None
    assert persisted.is_finalized is True
    assert persisted.failure_reason == JobFailureReason.CANCELLED
    assert persisted.finalized_at == cancel_at
    assert persisted.result_file_path is None
    assert persisted.result_inline_base64 is None


@pytest.mark.contract
@pytest.mark.integration
def test_release_expired_jobs_trigger_timeout_processing(
    postgres_queue: PostgresJobQueue,
    worker: InstrumentedWorker,
    job_service: DefaultJobService,
    make_job,
    time_controller: TimeController,
) -> None:
    """Expired jobs are released for timeout handling and cleaned up."""

    job = make_job(
        sync_timeout_sec=30,
        result_file_path="results/pending.bin",
        result_inline_base64="cHJldmlldyI=",
    )
    postgres_queue.enqueue(job)

    expired_now = time_controller.advance(seconds=45)
    assert expired_now > job.expires_at

    expired_jobs = list(postgres_queue.release_expired(now=expired_now))
    assert [item.id for item in expired_jobs] == [job.id]

    asyncio.run(worker.handle_timeout(job, now=expired_now))

    persisted = job_service.get_job(job.id)
    assert persisted is not None
    assert persisted.is_finalized is True
    assert persisted.failure_reason == JobFailureReason.TIMEOUT
    assert persisted.result_file_path is None
    assert persisted.result_inline_base64 is None
