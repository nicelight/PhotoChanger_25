"""Unit tests for DefaultJobService helper behaviour."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID

import pytest

from src.app.domain import calculate_result_expires_at
from src.app.domain.models import Job, JobFailureReason, JobStatus, MediaObject
from src.app.infrastructure.queue.postgres import PostgresJobQueue
from src.app.services.default import DefaultJobService
from src.app.services.job_service import QueueUnavailableError


@pytest.fixture
def job_service(postgres_queue: PostgresJobQueue) -> DefaultJobService:
    service = DefaultJobService(queue=postgres_queue)
    service.result_retention_hours = 72
    return service


def _build_job() -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=UUID("00000000-0000-0000-0000-000000000010"),
        slot_id="slot-001",
        status=JobStatus.PENDING,
        is_finalized=False,
        failure_reason=None,
        expires_at=now,
        created_at=now,
        updated_at=now,
        payload_path="payloads/sample",
    )


def test_fail_job_sets_failure_metadata(job_service: DefaultJobService) -> None:
    service = job_service
    job = _build_job()
    service.queue.enqueue(job)
    service.jobs[job.id] = job
    occurred_at = datetime.now(timezone.utc)

    updated = service.fail_job(
        job,
        failure_reason=JobFailureReason.TIMEOUT,
        occurred_at=occurred_at,
    )

    assert updated.is_finalized is True
    assert updated.failure_reason is JobFailureReason.TIMEOUT
    assert updated.finalized_at == occurred_at
    assert updated.updated_at == occurred_at
    assert service.get_job(job.id) is updated


def test_finalize_job_with_media_sets_result_fields(
    job_service: DefaultJobService,
) -> None:
    service = job_service
    job = _build_job()
    service.queue.enqueue(job)
    service.jobs[job.id] = job
    finalized_at = datetime.now(timezone.utc)
    media = MediaObject(
        id=UUID("00000000-0000-0000-0000-000000000011"),
        path="results/final.png",
        public_url="/media/results/final.png",
        expires_at=finalized_at + timedelta(hours=service.result_retention_hours),
        created_at=finalized_at,
        job_id=job.id,
        mime="image/png",
        size_bytes=1024,
    )

    persisted = service.finalize_job(
        job,
        finalized_at=finalized_at,
        result_media=media,
        inline_preview="ignored",
        result_checksum="sha256:d34db33f",
    )

    assert persisted.is_finalized is True
    assert persisted.result_inline_base64 is None
    assert persisted.result_file_path == "results/final.png"
    assert persisted.result_mime_type == "image/png"
    assert persisted.result_size_bytes == 1024
    assert persisted.result_checksum == "sha256:d34db33f"
    assert persisted.result_expires_at == media.expires_at
    assert service.get_job(job.id) is persisted


def test_finalize_job_without_media_sets_retention_ttl(
    job_service: DefaultJobService,
) -> None:
    service = job_service
    job = _build_job()
    service.queue.enqueue(job)
    service.jobs[job.id] = job
    finalized_at = datetime.now(timezone.utc)

    persisted = service.finalize_job(
        job,
        finalized_at=finalized_at,
        result_media=None,
        inline_preview=None,
        result_checksum=None,
    )

    assert persisted.result_file_path is None
    assert persisted.result_inline_base64 is None
    assert persisted.result_checksum is None
    assert persisted.result_mime_type is None
    assert persisted.result_size_bytes is None
    assert persisted.result_expires_at == calculate_result_expires_at(
        finalized_at, result_retention_hours=service.result_retention_hours
    )


def test_clear_inline_preview_resets_inline_fields(
    job_service: DefaultJobService,
) -> None:
    service = job_service
    job = _build_job()
    job.result_inline_base64 = "Zm9v"
    job.result_mime_type = "image/png"
    job.result_size_bytes = 42
    job.result_checksum = "deadbeef"
    service.jobs[job.id] = job

    cleared = service.clear_inline_preview(job)

    assert cleared.result_inline_base64 is None
    assert cleared.result_mime_type is None
    assert cleared.result_size_bytes is None
    assert cleared.result_checksum is None
    assert service.get_job(job.id) is cleared


class _QueueStub:
    def __init__(self) -> None:
        self.finalized: list[Job] = []

    def mark_finalized(self, job: Job) -> Job:
        self.finalized.append(job)
        return job


class _FailingQueueStub(_QueueStub):
    def mark_finalized(self, job: Job) -> Job:  # type: ignore[override]
        raise QueueUnavailableError("temporary failure")


def test_purge_expired_results_clears_metadata() -> None:
    queue = _QueueStub()
    service = DefaultJobService(queue=queue)  # type: ignore[arg-type]
    now = datetime.now(timezone.utc)
    job = _build_job()
    job.is_finalized = True
    original_file_path = "results/final.png"
    original_mime = "image/png"
    original_size = 128
    original_checksum = "sha256:deadbeef"
    original_expires_at = now - timedelta(seconds=1)
    job.result_file_path = original_file_path
    job.result_mime_type = original_mime
    job.result_size_bytes = original_size
    job.result_checksum = original_checksum
    job.result_expires_at = original_expires_at
    service.jobs[job.id] = job

    expired = service.purge_expired_results(now=now)

    assert expired == [job]
    assert job.result_file_path is None
    assert job.result_mime_type is None
    assert job.result_size_bytes is None
    assert job.result_checksum is None
    assert job.result_expires_at is None
    assert queue.finalized == [job]


def test_purge_expired_results_ignores_future_deadline() -> None:
    queue = _QueueStub()
    service = DefaultJobService(queue=queue)  # type: ignore[arg-type]
    now = datetime.now(timezone.utc)
    job = _build_job()
    job.is_finalized = True
    job.result_file_path = "results/final.png"
    future = now + timedelta(hours=1)
    job.result_expires_at = future
    service.jobs[job.id] = job

    expired = service.purge_expired_results(now=now)

    assert expired == []
    assert job.result_file_path == "results/final.png"
    assert job.result_expires_at == future
    assert queue.finalized == []


def test_purge_expired_results_restores_metadata_on_queue_failure() -> None:
    queue = _FailingQueueStub()
    service = DefaultJobService(queue=queue)  # type: ignore[arg-type]
    now = datetime.now(timezone.utc)
    job = _build_job()
    job.is_finalized = True
    job.result_file_path = "results/final.png"
    job.result_mime_type = "image/png"
    job.result_size_bytes = 128
    job.result_checksum = "sha256:deadbeef"
    job.result_expires_at = now - timedelta(seconds=1)
    service.jobs[job.id] = job

    expired = service.purge_expired_results(now=now)

    assert expired == [job]
    assert job.result_file_path == original_file_path
    assert job.result_mime_type == original_mime
    assert job.result_size_bytes == original_size
    assert job.result_checksum == original_checksum
    assert job.result_expires_at == original_expires_at
    assert queue.finalized == []
