"""Test doubles for the PostgreSQL queue implementation."""

from __future__ import annotations

from collections import defaultdict, deque
from dataclasses import replace
from datetime import datetime, timezone
from typing import Deque, Dict, Iterable, List
from uuid import UUID

from src.app.domain.models import Job, JobFailureReason, JobStatus, ProcessingLog
from src.app.infrastructure.queue.postgres import PostgresJobQueue, PostgresQueueConfig
from src.app.services.job_service import QueueBusyError


TEST_QUEUE_DSN = "postgresql://tests"


class InMemoryQueueBackend:
    """Lightweight backend used in tests instead of the real Postgres backend."""

    def __init__(self, config: PostgresQueueConfig) -> None:
        self._config = config
        self._jobs: Dict[UUID, Job] = {}
        self._pending: Deque[UUID] = deque()
        self._processing_logs: Dict[UUID, List[ProcessingLog]] = defaultdict(list)

    # Queue operations ---------------------------------------------------

    def enqueue(self, job: Job) -> Job:
        self._enforce_backpressure(now=job.created_at)
        job.status = JobStatus.PENDING
        job.is_finalized = False
        job.failure_reason = None
        if job.id not in self._jobs:
            self._pending.append(job.id)
        self._jobs[job.id] = job
        return job

    def acquire_for_processing(self, *, now: datetime) -> Job | None:
        for job_id in list(self._pending):
            job = self._jobs.get(job_id)
            if job is None:
                self._pending.remove(job_id)
                continue
            if job.is_finalized:
                self._pending.remove(job_id)
                continue
            if job.expires_at <= now:
                continue
            self._pending.remove(job_id)
            job.status = JobStatus.PROCESSING
            job.updated_at = now
            return job
        return None

    def mark_finalized(self, job: Job) -> Job:
        if job.id in self._pending:
            self._pending.remove(job.id)
        self._jobs[job.id] = job
        return job

    def release_expired(self, *, now: datetime) -> Iterable[Job]:
        released: list[Job] = []
        for job_id, job in list(self._jobs.items()):
            if job.is_finalized or job.expires_at > now:
                continue
            job.is_finalized = True
            job.failure_reason = JobFailureReason.TIMEOUT
            job.status = JobStatus.PROCESSING
            job.updated_at = now
            job.finalized_at = now
            if job_id in self._pending:
                self._pending.remove(job_id)
            released.append(job)
        return released

    def append_processing_logs(self, logs: Iterable[ProcessingLog]) -> None:
        for log in logs:
            stored = replace(log)
            stored.occurred_at = _ensure_timezone(stored.occurred_at)
            self._processing_logs[stored.job_id].append(stored)

    def list_processing_logs(self, job_id: UUID) -> list[ProcessingLog]:
        return [replace(log) for log in self._processing_logs.get(job_id, [])]

    # Helpers ------------------------------------------------------------

    def _enforce_backpressure(self, *, now: datetime) -> None:
        limit = self._config.max_in_flight_jobs
        if limit is None:
            return
        active = sum(
            1
            for job in self._jobs.values()
            if not job.is_finalized and job.expires_at >= now
        )
        if active >= limit:
            raise QueueBusyError("ingest queue saturated")


def build_test_queue(*, max_in_flight_jobs: int | None = None) -> PostgresJobQueue:
    """Create :class:`PostgresJobQueue` wired to the in-memory backend."""

    config = PostgresQueueConfig(
        dsn=TEST_QUEUE_DSN, max_in_flight_jobs=max_in_flight_jobs
    )
    backend = InMemoryQueueBackend(config)
    return PostgresJobQueue(config=config, backend=backend)


def _ensure_timezone(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


__all__ = ["InMemoryQueueBackend", "build_test_queue", "TEST_QUEUE_DSN"]
