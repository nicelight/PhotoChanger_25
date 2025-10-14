"""Repository interface for statistics aggregation."""

from __future__ import annotations

from datetime import datetime
from typing import Mapping

from ..domain.models import ProcessingLog, Slot


class StatsRepository:
    """Provides raw counters for dashboards and monitoring exporters."""

    def collect_global_metrics(
        self, *, since: datetime | None = None
    ) -> Mapping[str, int]:
        """Aggregate totals across all jobs."""

        raise NotImplementedError

    def collect_slot_metrics(
        self, slot: Slot, *, since: datetime | None = None
    ) -> Mapping[str, int]:
        """Aggregate metrics limited to a specific slot."""

        raise NotImplementedError

    def store_processing_log(self, log: ProcessingLog) -> None:
        """Persist a processing log entry for further aggregation."""

        raise NotImplementedError
