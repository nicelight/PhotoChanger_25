"""Worker skeleton that processes queue jobs."""

from __future__ import annotations

from datetime import datetime

from ..domain.models import Job
from ..services import JobService, MediaService, SettingsService, StatsService


class QueueWorker:
    """Coordinates picking jobs, dispatching to providers and persisting results."""

    def __init__(
        self,
        *,
        job_service: JobService,
        media_service: MediaService,
        settings_service: SettingsService,
        stats_service: StatsService,
    ) -> None:
        self.job_service = job_service
        self.media_service = media_service
        self.settings_service = settings_service
        self.stats_service = stats_service

    def run_once(self, *, now: datetime) -> None:
        """Pick and process at most one job within the ``T_sync_response`` window."""

        raise NotImplementedError

    def process_job(self, job: Job, *, now: datetime) -> None:
        """Execute provider-specific logic keeping ``job.expires_at`` in mind.

        Implementations must finalize the job within ``T_sync_response`` and
        persist ``result_expires_at = finalized_at + T_result_retention`` for
        successful outcomes, coordinating with :class:`MediaService`.
        """

        raise NotImplementedError

    def handle_timeout(self, job: Job, *, now: datetime) -> None:
        """Mark the job as timed out when ``now`` exceeds ``job.expires_at``."""

        raise NotImplementedError

    def dispatch_to_provider(self, job: Job) -> None:
        """Delegate processing to the configured provider adapter."""

        raise NotImplementedError
