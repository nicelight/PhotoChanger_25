"""Statistics service interface."""

from __future__ import annotations

from datetime import datetime

from ..domain.models import ProcessingLog, Slot
from ..schemas.stats import StatsAggregation, StatsWindow


class StatsService:
    """Aggregates job/slot metrics for dashboards and monitoring."""

    def collect_global_stats(
        self,
        *,
        window: StatsWindow = StatsWindow.DAY,
        since: datetime | None = None,
        now: datetime | None = None,
    ) -> StatsAggregation:
        """Return aggregated counters for all jobs within ``window``."""

        raise NotImplementedError

    def collect_slot_stats(
        self,
        slot: Slot,
        *,
        window: StatsWindow = StatsWindow.DAY,
        since: datetime | None = None,
        now: datetime | None = None,
    ) -> StatsAggregation:
        """Return metrics scoped to a single slot for the chosen ``window``."""

        raise NotImplementedError

    def record_processing_event(self, log: ProcessingLog) -> None:
        """Persist a new processing log record for future aggregation."""

        raise NotImplementedError
