"""Unit tests for DefaultJobService helper behaviour."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from src.app.domain.models import Job, JobFailureReason, JobStatus
from src.app.services.default import DefaultJobService
from tests.mocks.queue import build_test_queue


def _create_service() -> DefaultJobService:
    queue = build_test_queue()
    return DefaultJobService(queue=queue)


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


def test_fail_job_sets_failure_metadata() -> None:
    service = _create_service()
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


def test_clear_inline_preview_resets_inline_fields() -> None:
    service = _create_service()
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
