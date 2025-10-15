"""Job service interface for coordinating queue operations.

The implementation will orchestrate interactions between the PostgreSQL queue,
media storage and provider adapters. Business logic is not implemented at this
stage; methods only define contracts in terms of domain models.
"""

from __future__ import annotations

from datetime import datetime
from typing import Iterable
from uuid import UUID

from ..domain.models import (
    Job,
    JobFailureReason,
    MediaObject,
    ProcessingLog,
    Settings,
    Slot,
)


class JobService:
    """High-level API for ingest job lifecycle management."""

    def create_job(
        self,
        slot: Slot,
        *,
        payload: MediaObject | None,
        settings: Settings,
        job_id: UUID | None = None,
        created_at: datetime | None = None,
    ) -> Job:
        """Create a new job for the provided slot and payload.

        Implementations must calculate ``job.expires_at`` as
        ``job.created_at + settings.ingest.sync_response_timeout_sec`` to follow
        the contract from ``domain-model.md`` and persist the job via the queue
        repository.
        """

        raise NotImplementedError

    def acquire_next_job(self, *, now: datetime) -> Job | None:
        """Pull the next job respecting ``expires_at`` and SKIP LOCKED semantics."""

        raise NotImplementedError

    def finalize_job(
        self,
        job: Job,
        *,
        finalized_at: datetime,
        result_media: MediaObject | None,
        inline_preview: str | None,
    ) -> Job:
        """Finalize a job and persist 72h retention metadata.

        ``result_media`` should represent the stored result artifact whose
        ``expires_at`` equals ``finalized_at + T_result_retention`` (72h). The
        method is also responsible for clearing inline previews once the HTTP
        response is delivered.
        """

        raise NotImplementedError

    def fail_job(
        self,
        job: Job,
        *,
        failure_reason: JobFailureReason,
        occurred_at: datetime,
    ) -> Job:
        """Mark a job as failed and propagate timeout/cancellation reasons.

        ``failure_reason`` must match one of the values defined in
        :class:`JobFailureReason` (``timeout``, ``provider_error`` or
        ``cancelled``), aligning with ``spec/contracts/schemas/Job.json``.
        """

        raise NotImplementedError

    def append_processing_logs(self, job: Job, logs: Iterable[ProcessingLog]) -> None:
        """Persist processing logs describing provider interactions."""

        raise NotImplementedError

    def refresh_recent_results(self, slot: Slot, *, limit: int = 10) -> Slot:
        """Update ``slot.recent_results`` with recent finalized jobs.

        The returned slot should include gallery metadata matching the
        ``Result`` schema: ``thumbnail_url``/``download_url`` pairs and
        ``result_expires_at`` calculated as ``finalized_at + T_result_retention``.
        """

        raise NotImplementedError
