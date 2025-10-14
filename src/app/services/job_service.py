"""Job service interface for coordinating queue operations.

The implementation will orchestrate interactions between the PostgreSQL queue,
media storage and provider adapters. Business logic is not implemented at this
stage; methods only define contracts in terms of domain models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..domain.models import Job, MediaObject, ProcessingLog, Settings, Slot


class JobService:
    """High-level API for ingest job lifecycle management."""

    def create_job(
        self,
        slot: Slot,
        *,
        payload: MediaObject | None,
        settings: Settings,
    ) -> Job:
        """Create a new job for the provided slot and payload."""

        raise NotImplementedError

    def acquire_next_job(self, *, now: datetime) -> Job | None:
        """Pull the next job from the queue respecting ``expires_at`` deadlines."""

        raise NotImplementedError

    def finalize_job(
        self,
        job: Job,
        *,
        finalized_at: datetime,
        result_media: MediaObject | None,
        inline_preview: str | None,
    ) -> Job:
        """Finalize a job and persist 72h retention metadata."""

        raise NotImplementedError

    def fail_job(
        self,
        job: Job,
        *,
        failure_reason: str,
        occurred_at: datetime,
    ) -> Job:
        """Mark a job as failed and propagate timeout/cancellation reasons."""

        raise NotImplementedError

    def append_processing_logs(
        self, job: Job, logs: Iterable[ProcessingLog]
    ) -> None:
        """Persist processing logs describing provider interactions."""

        raise NotImplementedError

    def refresh_recent_results(self, slot: Slot, *, limit: int = 10) -> Slot:
        """Update slot.recent_results with the latest successful jobs."""

        raise NotImplementedError
