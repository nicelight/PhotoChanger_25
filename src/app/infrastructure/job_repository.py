"""Repository interface for the PostgreSQL-backed job queue."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..domain.models import Job


class JobRepository:
    """Persistence gateway for queue operations.

    Implementations use PostgreSQL with ``SELECT … FOR UPDATE SKIP LOCKED`` to
    avoid head-of-line blocking and enforce the unified deadline
    ``T_sync_response`` stored in ``Job.expires_at``.
    """

    def enqueue(self, job: Job) -> Job:
        """Persist a freshly created job and its ``expires_at`` deadline."""

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
