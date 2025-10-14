"""PostgreSQL queue scaffolding aligned with blueprint constraints."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable

from app.domain.models import Job
from ..job_repository import JobRepository


@dataclass(slots=True)
class PostgresQueueConfig:
    """Configuration required to talk to the queue database."""

    dsn: str
    poll_interval_seconds: float = 1.0
    max_batch_size: int = 1
    statement_timeout_ms: int = 5_000


class PostgresJobQueue(JobRepository):
    """Concrete repository placeholder using PostgreSQL SKIP LOCKED semantics.

    The real implementation will rely on ``SELECT … FOR UPDATE SKIP LOCKED``
    queries to acquire pending jobs, as mandated by
    ``spec/docs/blueprints/domain-model.md`` and the phase 2 scope. This stub
    simply captures the contract and expected dependencies.
    """

    def __init__(self, *, config: PostgresQueueConfig) -> None:
        self.config = config

    def enqueue(self, job: Job) -> Job:  # type: ignore[override]
        """Persist a new job into the PostgreSQL queue."""

        raise NotImplementedError

    def acquire_for_processing(self, *, now: datetime) -> Job | None:  # type: ignore[override]
        """Select the next job using ``FOR UPDATE SKIP LOCKED`` semantics."""

        raise NotImplementedError

    def mark_finalized(self, job: Job) -> Job:  # type: ignore[override]
        """Update the job row after worker finalisation."""

        raise NotImplementedError

    def release_expired(self, *, now: datetime) -> Iterable[Job]:  # type: ignore[override]
        """Return jobs that exceeded ``T_sync_response`` for timeout handling."""

        raise NotImplementedError
