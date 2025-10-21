"""Repository interface for statistics aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable

from ..domain.models import ProcessingLog, Slot, SlotRecentResult
from ..schemas.stats import StatsMetric, StatsWindow


class StatsRepository:
    """Provides raw counters for dashboards and monitoring exporters."""

    def collect_global_metrics(
        self,
        *,
        window: StatsWindow,
        since: datetime | None = None,
    ) -> Iterable[StatsMetric]:
        """Return time-series metrics across all jobs."""

        raise NotImplementedError

    def collect_slot_metrics(
        self,
        slot: Slot,
        *,
        window: StatsWindow,
        since: datetime | None = None,
    ) -> Iterable[StatsMetric]:
        """Return metrics limited to a specific slot."""

        raise NotImplementedError

    def store_processing_log(self, log: ProcessingLog) -> None:
        """Persist a processing log entry for further aggregation."""

        raise NotImplementedError

    def load_recent_results(
        self,
        slot: Slot,
        *,
        since: datetime,
        limit: int,
        now: datetime,
    ) -> Iterable[SlotRecentResult]:
        """Return slot recent results ordered by completion time."""

        raise NotImplementedError
