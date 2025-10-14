"""Repository interface for the PostgreSQL-backed job queue."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..domain.models import Job


class JobRepository:
    """Persistence gateway for queue operations."""

    def enqueue(self, job: Job) -> Job:
        """Persist a freshly created job."""

        raise NotImplementedError

    def acquire_for_processing(self, *, now: datetime) -> Job | None:
        """Lock the next job using ``SELECT … FOR UPDATE SKIP LOCKED`` semantics."""

        raise NotImplementedError

    def mark_finalized(self, job: Job) -> Job:
        """Persist finalization metadata including ``result_expires_at``."""

        raise NotImplementedError

    def release_expired(self, *, now: datetime) -> Iterable[Job]:
        """Return jobs that exceeded ``T_sync_response`` and mark them failed."""

        raise NotImplementedError
