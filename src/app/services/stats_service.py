"""Statistics service interface."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from ..domain.models import ProcessingLog, Slot


class StatsService:
    """Aggregates job/slot metrics for dashboards and monitoring."""

    def collect_global_stats(self, *, since: datetime | None = None) -> Mapping[str, int]:
        """Return aggregated counters (success/fail/timeout) for all jobs."""

        raise NotImplementedError

    def collect_slot_stats(self, slot: Slot, *, since: datetime | None = None) -> Mapping[str, int]:
        """Return metrics scoped to a single slot."""

        raise NotImplementedError

    def record_processing_event(self, log: ProcessingLog) -> None:
        """Persist a new processing log record for future aggregation."""

        raise NotImplementedError
