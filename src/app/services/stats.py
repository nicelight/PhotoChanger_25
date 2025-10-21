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


SLOT_DEFAULT_RANGE = timedelta(days=14)
SLOT_MAX_RANGE = timedelta(days=31)
GLOBAL_DEFAULT_RANGE = timedelta(weeks=8)
GLOBAL_MAX_RANGE = timedelta(days=90)
SLOT_CACHE_TTL = timedelta(minutes=5)
GLOBAL_CACHE_TTL = timedelta(minutes=1)
_DEFAULT_RANGE_SENTINEL = object()


class CachedStatsService(StatsService):
    """Provide cached statistics aggregations with event-driven invalidation."""

    def __init__(
        self,
        repository: StatsRepository,
        *,
        slot_ttl: timedelta = SLOT_CACHE_TTL,
        global_ttl: timedelta = GLOBAL_CACHE_TTL,
        clock: Callable[[], datetime] | None = None,
    ) -> None:
        if slot_ttl < timedelta(0):
            raise ValueError("slot_ttl must be non-negative")
        if global_ttl < timedelta(0):
            raise ValueError("global_ttl must be non-negative")
        self._repository = repository
        self._slot_ttl = slot_ttl
        self._global_ttl = global_ttl
        self._clock = clock or _default_clock
        self._cache: Dict[Tuple[str | None, StatsWindow, object], _CacheEntry] = {}

    def collect_global_stats(
        self,
        *,
        window: StatsWindow = StatsWindow.WEEK,
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
        normalized_since = self._normalise_since(
            slot=slot, window=window, since=since, now=now
        )
        cache_since = normalized_since if since is not None else _DEFAULT_RANGE_SENTINEL
        key = (slot.id if slot else None, window, cache_since)
        ttl = self._select_ttl(slot)
        entry = self._cache.get(key) if ttl > timedelta(0) else None
        if entry is not None and entry.is_valid(now=now):
            return entry.aggregation

        metrics = self._load_metrics(slot, window=window, since=normalized_since)
        aggregation = StatsAggregation.from_metrics(window, metrics)
        if ttl > timedelta(0):
            self._cache[key] = _CacheEntry(
                aggregation=aggregation,
                expires_at=now + ttl,
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

    def _normalise_since(
        self,
        *,
        slot: Slot | None,
        window: StatsWindow,
        since: datetime | None,
        now: datetime,
    ) -> datetime:
        _ = window  # reserved for future granularity-specific logic
        if slot is None:
            default_range = GLOBAL_DEFAULT_RANGE
            max_range = GLOBAL_MAX_RANGE
        else:
            default_range = SLOT_DEFAULT_RANGE
            max_range = SLOT_MAX_RANGE
        lower_bound = now - max_range
        candidate = since or (now - default_range)
        if candidate < lower_bound:
            candidate = lower_bound
        if candidate > now:
            candidate = now
        return candidate

    def _select_ttl(self, slot: Slot | None) -> timedelta:
        return self._slot_ttl if slot is not None else self._global_ttl

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


__all__ = [
    "CachedStatsService",
    "GLOBAL_CACHE_TTL",
    "GLOBAL_DEFAULT_RANGE",
    "GLOBAL_MAX_RANGE",
    "SLOT_CACHE_TTL",
    "SLOT_DEFAULT_RANGE",
    "SLOT_MAX_RANGE",
]

