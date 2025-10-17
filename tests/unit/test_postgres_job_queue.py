from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.app.domain.models import Job, JobFailureReason, JobStatus, ProcessingLog, ProcessingStatus
from src.app.infrastructure.queue.postgres import PostgresJobQueue, PostgresQueueConfig
from src.app.services.job_service import QueueBusyError


def _queue(max_in_flight: int | None = None) -> PostgresJobQueue:
    return PostgresJobQueue(
        config=PostgresQueueConfig(dsn=":memory:", max_in_flight_jobs=max_in_flight)
    )


def _job(*, expires_delta: timedelta = timedelta(minutes=1)) -> Job:
    now = datetime.now(timezone.utc)
    return Job(
        id=uuid4(),
        slot_id="slot-1",
        status=JobStatus.PENDING,
        is_finalized=False,
        failure_reason=None,
        expires_at=now + expires_delta,
        created_at=now,
        updated_at=now,
    )


def test_enqueue_and_acquire_updates_status() -> None:
    queue = _queue()
    job = _job()

    queue.enqueue(job)
    acquired = queue.acquire_for_processing(now=datetime.now(timezone.utc))

    assert acquired is not None
    assert acquired.id == job.id
    assert acquired.status is JobStatus.PROCESSING


def test_backpressure_limit_blocks_enqueue() -> None:
    queue = _queue(max_in_flight=1)
    queue.enqueue(_job())

    with pytest.raises(QueueBusyError):
        queue.enqueue(_job())


def test_release_expired_marks_timeout() -> None:
    queue = _queue()
    expired_job = _job(expires_delta=-timedelta(minutes=1))
    queue.enqueue(expired_job)

    released = list(queue.release_expired(now=datetime.now(timezone.utc)))

    assert len(released) == 1
    job = released[0]
    assert job.failure_reason is JobFailureReason.TIMEOUT
    assert job.is_finalized is True


def test_mark_finalized_persists_result_metadata() -> None:
    queue = _queue()
    job = _job()
    queue.enqueue(job)
    acquired = queue.acquire_for_processing(now=datetime.now(timezone.utc))
    assert acquired is not None
    acquired.result_inline_base64 = "Zm9v"
    acquired.result_file_path = "results/file.png"
    acquired.result_mime_type = "image/png"
    acquired.result_size_bytes = 42
    acquired.is_finalized = True
    acquired.finalized_at = datetime.now(timezone.utc)
    acquired.updated_at = acquired.finalized_at

    persisted = queue.mark_finalized(acquired)

    assert persisted.is_finalized is True
    assert persisted.result_file_path == "results/file.png"
    assert persisted.result_inline_base64 == "Zm9v"


def test_append_processing_logs_persists_records() -> None:
    queue = _queue()
    job = _job()
    queue.enqueue(job)
    log = ProcessingLog(
        id=uuid4(),
        job_id=job.id,
        slot_id=job.slot_id,
        status=ProcessingStatus.RECEIVED,
        occurred_at=datetime.now(timezone.utc),
        message="received",
    )

    queue.append_processing_logs([log])

    stored_logs = queue.list_processing_logs(job.id)

    assert len(stored_logs) == 1
    assert stored_logs[0].status is ProcessingStatus.RECEIVED
