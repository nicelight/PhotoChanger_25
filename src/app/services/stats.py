"""Statistics service implementation backed by a repository and TTL cache."""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Callable, Dict, Iterable, Sequence, Tuple, cast

from ..domain.models import ProcessingLog, Slot, SlotRecentResult
from ..infrastructure.stats_repository import StatsRepository
from ..schemas.stats import StatsAggregation, StatsMetric, StatsWindow
from .stats_service import StatsService


def _default_clock() -> datetime:
    return datetime.now(timezone.utc)


@dataclass(slots=True)
class _CacheEntry:
    value: object
    expires_at: datetime

    def is_valid(self, *, now: datetime) -> bool:
        return now < self.expires_at


SLOT_DEFAULT_RANGE = timedelta(days=14)
SLOT_MAX_RANGE = timedelta(days=31)
GLOBAL_DEFAULT_RANGE = timedelta(weeks=8)
GLOBAL_MAX_RANGE = timedelta(days=90)
SLOT_CACHE_TTL = timedelta(minutes=5)
GLOBAL_CACHE_TTL = timedelta(minutes=1)
RECENT_RESULTS_LIMIT = 10
RECENT_RESULTS_RETENTION = timedelta(hours=72)
_DEFAULT_RANGE_SENTINEL = object()
_RECENT_RESULTS_CACHE_KEY = "recent_results"


class CachedStatsService(StatsService):
    """Provide cached statistics aggregations with event-driven invalidation."""

    def __init__(
        self,
        repository: StatsRepository,
        *,
        slot_ttl: timedelta = SLOT_CACHE_TTL,
        global_ttl: timedelta = GLOBAL_CACHE_TTL,
        recent_results_retention: timedelta = RECENT_RESULTS_RETENTION,
        recent_results_limit: int = RECENT_RESULTS_LIMIT,
        clock: Callable[[], datetime] | None = None,
        max_record_attempts: int = 3,
        record_retry_delay: float = 0.0,
        logger: logging.Logger | None = None,
    ) -> None:
        if slot_ttl < timedelta(0):
            raise ValueError("slot_ttl must be non-negative")
        if global_ttl < timedelta(0):
            raise ValueError("global_ttl must be non-negative")
        if recent_results_retention <= timedelta(0):
            raise ValueError("recent_results_retention must be positive")
        if recent_results_limit < 1:
            raise ValueError("recent_results_limit must be at least 1")
        if max_record_attempts < 1:
            raise ValueError("max_record_attempts must be at least 1")
        if record_retry_delay < 0:
            raise ValueError("record_retry_delay cannot be negative")
        self._repository = repository
        self._slot_ttl = slot_ttl
        self._global_ttl = global_ttl
        self._recent_results_retention = recent_results_retention
        self._recent_results_limit = recent_results_limit
        self._clock = clock or _default_clock
        self._cache: Dict[Tuple[object, ...], _CacheEntry] = {}
        self._max_record_attempts = max_record_attempts
        self._record_retry_delay = record_retry_delay
        self._logger = logger or logging.getLogger(__name__)

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
        attempt = 0
        last_error: Exception | None = None
        while attempt < self._max_record_attempts:
            attempt += 1
            try:
                self._repository.store_processing_log(log)
            except Exception as exc:  # pragma: no cover - defensive logging
                last_error = exc
                self._logger.warning(
                    "Failed to store processing log (attempt %s/%s)",
                    attempt,
                    self._max_record_attempts,
                    exc_info=exc,
                    extra={"slot_id": log.slot_id, "job_id": str(log.job_id)},
                )
                if attempt >= self._max_record_attempts:
                    break
                if self._record_retry_delay > 0:
                    time.sleep(self._record_retry_delay * attempt)
                continue
            else:
                self._invalidate(slot_id=log.slot_id)
                return
        if last_error is not None:
            raise last_error

    def recent_results(
        self,
        slot: Slot,
        *,
        now: datetime | None = None,
    ) -> list[SlotRecentResult]:
        current_time = now or self._clock()
        ttl = self._select_ttl(slot)
        key = (slot.id, _RECENT_RESULTS_CACHE_KEY)
        entry = self._cache.get(key) if ttl > timedelta(0) else None
        if entry is not None and entry.is_valid(now=current_time):
            cached = cast(Sequence[SlotRecentResult], entry.value)
            return [self._clone_recent(item) for item in cached]

        since = current_time - self._recent_results_retention
        results = list(
            self._repository.load_recent_results(
                slot,
                since=since,
                limit=self._recent_results_limit,
                now=current_time,
            )
        )
        normalized = [
            self._clone_recent(item)
            for item in results
            if item["completed_at"] >= since
            and item["result_expires_at"] > current_time
        ]
        normalized.sort(key=lambda item: item["completed_at"], reverse=True)
        limited = normalized[: self._recent_results_limit]
        if ttl > timedelta(0):
            self._cache[key] = _CacheEntry(
                value=tuple(limited),
                expires_at=current_time + ttl,
            )
        return limited

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
            return cast(StatsAggregation, entry.value)

        metrics = self._load_metrics(slot, window=window, since=normalized_since)
        aggregation = StatsAggregation.from_metrics(window, metrics)
        if ttl > timedelta(0):
            self._cache[key] = _CacheEntry(
                value=aggregation,
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

    @staticmethod
    def _clone_recent(result: SlotRecentResult) -> SlotRecentResult:
        return cast(SlotRecentResult, dict(result))


__all__ = [
    "CachedStatsService",
    "GLOBAL_CACHE_TTL",
    "GLOBAL_DEFAULT_RANGE",
    "GLOBAL_MAX_RANGE",
    "SLOT_CACHE_TTL",
    "SLOT_DEFAULT_RANGE",
    "SLOT_MAX_RANGE",
]

