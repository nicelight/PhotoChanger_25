"""Data structures describing statistics aggregations for admin dashboards."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Iterable, Mapping


class StatsWindow(str, Enum):
    """Supported aggregation windows for time-series statistics."""

    DAY = "day"
    WEEK = "week"


@dataclass(slots=True)
class StatsCounters:
    """Normalised set of counters shared between global and slot metrics."""

    success: int = 0
    timeouts: int = 0
    provider_errors: int = 0
    cancelled: int = 0
    errors: int = 0
    ingest_count: int = 0

    @classmethod
    def from_mapping(cls, counters: Mapping[str, int] | None) -> "StatsCounters":
        """Build counters from a repository payload guarding against gaps."""

        if counters is None:
            return cls()
        return cls(
            success=max(int(counters.get("success", 0)), 0),
            timeouts=max(int(counters.get("timeouts", 0)), 0),
            provider_errors=max(int(counters.get("provider_errors", 0)), 0),
            cancelled=max(int(counters.get("cancelled", 0)), 0),
            errors=max(int(counters.get("errors", 0)), 0),
            ingest_count=max(int(counters.get("ingest_count", 0)), 0),
        )

    def add(self, other: "StatsCounters") -> "StatsCounters":
        """Return a new :class:`StatsCounters` with aggregated values."""

        return StatsCounters(
            success=self.success + other.success,
            timeouts=self.timeouts + other.timeouts,
            provider_errors=self.provider_errors + other.provider_errors,
            cancelled=self.cancelled + other.cancelled,
            errors=self.errors + other.errors,
            ingest_count=self.ingest_count + other.ingest_count,
        )

    @property
    def total_runs(self) -> int:
        """Total number of processed jobs derived from success/failure counters."""

        return (
            self.success
            + self.timeouts
            + self.provider_errors
            + self.cancelled
            + self.errors
        )


@dataclass(slots=True)
class StatsMetric:
    """Single time-series point returned by the statistics repository."""

    period_start: datetime
    period_end: datetime
    counters: StatsCounters


@dataclass(slots=True)
class StatsSummary:
    """Aggregated counters normalised for API responses."""

    total_runs: int
    success: int
    timeouts: int
    provider_errors: int
    cancelled: int
    errors: int
    ingest_count: int

    @classmethod
    def from_counters(cls, counters: StatsCounters) -> "StatsSummary":
        """Create a summary snapshot from accumulated counters."""

        return cls(
            total_runs=counters.total_runs,
            success=counters.success,
            timeouts=counters.timeouts,
            provider_errors=counters.provider_errors,
            cancelled=counters.cancelled,
            errors=counters.errors,
            ingest_count=counters.ingest_count,
        )

    @property
    def failure_count(self) -> int:
        """Number of failed runs derived from total and successful counters."""

        return max(self.total_runs - self.success, 0)


@dataclass(slots=True)
class StatsAggregation:
    """Structured representation of aggregated statistics for a window."""

    window: StatsWindow
    metrics: list[StatsMetric]
    summary: StatsSummary

    @classmethod
    def from_metrics(
        cls, window: StatsWindow, metrics: Iterable[StatsMetric]
    ) -> "StatsAggregation":
        """Produce an aggregation with precalculated summary counters."""

        items = list(metrics)
        total = StatsCounters()
        for metric in items:
            total = total.add(metric.counters)
        return cls(window=window, metrics=items, summary=StatsSummary.from_counters(total))


__all__ = [
    "StatsAggregation",
    "StatsCounters",
    "StatsMetric",
    "StatsSummary",
    "StatsWindow",
]

