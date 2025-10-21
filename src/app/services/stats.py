"""Statistics service implementation backed by a repository and TTL cache."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, Tuple

from ..domain.models import ProcessingLog, Slot
from ..infrastructure.stats_repository import StatsRepository
from ..schemas.stats import StatsAggregation, StatsMetric, StatsWindow
from .stats_service import StatsService


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class _CacheEntry:
    aggregation: StatsAggregation
    expires_at: datetime

    def is_valid(self, *, now: datetime) -> bool:
        return now < self.expires_at


class CachedStatsService(StatsService):
    """Provide cached statistics aggregations with event-driven invalidation."""

    def __init__(
        self,
        repository: StatsRepository,
        *,
        ttl: timedelta = timedelta(seconds=60),
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if ttl < timedelta(0):
            raise ValueError("ttl must be non-negative")
        self._repository = repository
        self._ttl = ttl
        self._clock = clock or _default_clock
        self._cache: Dict[Tuple[str | None, StatsWindow, datetime | None], _CacheEntry] = {}

    @property
    def _cache_enabled(self) -> bool:
        return self._ttl > timedelta(0)

    def collect_global_stats(
        self,
        *,
        window: StatsWindow = StatsWindow.DAY,
        since: datetime | None = None,
        now: datetime | None = None,
    ) -> StatsAggregation:
        current_time = now or self._clock()
        return self._collect(None, window=window, since=since, now=current_time)

    def collect_slot_stats(
        self,
        slot: Slot,
        *,
        window: StatsWindow = StatsWindow.DAY,
        since: datetime | None = None,
        now: datetime | None = None,
    ) -> StatsAggregation:
        current_time = now or self._clock()
        return self._collect(slot, window=window, since=since, now=current_time)

    def record_processing_event(self, log: ProcessingLog) -> None:
        store_log = getattr(self._repository, "store_processing_log", None)
        if callable(store_log):
            try:
                store_log(log)
            except NotImplementedError:
                pass
        self._invalidate(slot_id=log.slot_id)

    def _collect(
        self,
        slot: Slot | None,
        *,
        window: StatsWindow,
        since: datetime | None,
        now: datetime,
    ) -> StatsAggregation:
        key = (slot.id if slot else None, window, since)
        entry = self._cache.get(key)
        if entry is not None and self._cache_enabled and entry.is_valid(now=now):
            return entry.aggregation

        metrics = self._load_metrics(slot, window=window, since=since)
        aggregation = StatsAggregation.from_metrics(window, metrics)
        if self._cache_enabled:
            self._cache[key] = _CacheEntry(
                aggregation=aggregation,
                expires_at=now + self._ttl,
            )
        return aggregation

    def _load_metrics(
        self,
        slot: Slot | None,
        *,
        window: StatsWindow,
        since: datetime | None,
    ) -> Iterable[StatsMetric]:
        if slot is None:
            return list(
                self._repository.collect_global_metrics(window=window, since=since)
            )
        return list(
            self._repository.collect_slot_metrics(slot, window=window, since=since)
        )

    def _invalidate(self, *, slot_id: str | None) -> None:
        if not self._cache:
            return
        keys_to_remove = [
            key
            for key in self._cache
            if key[0] is None or slot_id is None or key[0] == slot_id
        ]
        for key in keys_to_remove:
            self._cache.pop(key, None)


__all__ = ["CachedStatsService"]

