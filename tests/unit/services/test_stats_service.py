from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import UUID, uuid4

import pytest

from src.app.domain.models import (
    ProcessingLog,
    ProcessingStatus,
    Slot,
    SlotRecentResult,
)
from src.app.schemas.stats import StatsCounters, StatsMetric, StatsWindow
from src.app.services.stats import CachedStatsService


class StubStatsRepository:
    def __init__(self) -> None:
        self.global_data: dict[StatsWindow, list[StatsMetric]] = {}
        self.slot_data: dict[tuple[str, StatsWindow], list[StatsMetric]] = {}
        self.global_calls: list[tuple[StatsWindow, datetime | None]] = []
        self.slot_calls: list[tuple[str, StatsWindow, datetime | None]] = []
        self.stored_logs: list[ProcessingLog] = []
        self.recent_results_data: dict[str, list[SlotRecentResult]] = {}
        self.recent_results_calls: list[
            tuple[str, datetime, int, datetime]
        ] = []
        self.store_failures: int = 0

    def collect_global_metrics(
        self, *, window: StatsWindow, since: datetime | None = None
    ) -> list[StatsMetric]:
        self.global_calls.append((window, since))
        return list(self.global_data.get(window, []))

    def collect_slot_metrics(
        self, slot: Slot, *, window: StatsWindow, since: datetime | None = None
    ) -> list[StatsMetric]:
        self.slot_calls.append((slot.id, window, since))
        return list(self.slot_data.get((slot.id, window), []))

    def store_processing_log(self, log: ProcessingLog) -> None:
        if self.store_failures > 0:
            self.store_failures -= 1
            raise RuntimeError("transient failure")
        self.stored_logs.append(log)

    def load_recent_results(
        self,
        slot: Slot,
        *,
        since: datetime,
        limit: int,
        now: datetime,
    ) -> list[SlotRecentResult]:
        self.recent_results_calls.append((slot.id, since, limit, now))
        return list(self.recent_results_data.get(slot.id, []))


def _build_metric(
    start: datetime,
    *,
    success: int = 0,
    timeouts: int = 0,
    provider_errors: int = 0,
    cancelled: int = 0,
    errors: int = 0,
    ingest_count: int = 0,
) -> StatsMetric:
    return StatsMetric(
        period_start=start,
        period_end=start + timedelta(days=1),
        counters=StatsCounters(
            success=success,
            timeouts=timeouts,
            provider_errors=provider_errors,
            cancelled=cancelled,
            errors=errors,
            ingest_count=ingest_count,
        ),
    )


def _build_recent_result(
    *,
    job_id: UUID,
    completed_at: datetime,
    expires_at: datetime,
    mime: str = "image/png",
    size: int | None = None,
) -> SlotRecentResult:
    result: SlotRecentResult = {
        "job_id": job_id,
        "thumbnail_url": f"/media/results/{job_id}",
        "download_url": f"/public/results/{job_id}",
        "completed_at": completed_at,
        "result_expires_at": expires_at,
        "mime": mime,
    }
    if size is not None:
        result["size_bytes"] = size
    return result


@pytest.mark.unit
def test_collect_global_stats_builds_summary_and_caches_metrics() -> None:
    now = datetime(2025, 1, 1, tzinfo=timezone.utc)
    repository = StubStatsRepository()
    repository.global_data[StatsWindow.DAY] = [
        _build_metric(now - timedelta(days=1), success=3, ingest_count=3),
        _build_metric(now - timedelta(days=2), timeouts=2, errors=1, ingest_count=3),
    ]
    service = CachedStatsService(
        repository,
        global_ttl=timedelta(seconds=30),
        clock=lambda: now,
    )

    aggregation = service.collect_global_stats(window=StatsWindow.DAY, now=now)

    assert aggregation.summary.total_runs == 6
    assert aggregation.summary.success == 3
    assert aggregation.summary.failure_count == 3
    assert aggregation.summary.ingest_count == 6
    assert len(aggregation.metrics) == 2
    assert repository.global_calls == [
        (StatsWindow.DAY, now - timedelta(weeks=8)),
    ]

    second = service.collect_global_stats(window=StatsWindow.DAY, now=now + timedelta(seconds=10))
    assert second is aggregation
    assert repository.global_calls == [
        (StatsWindow.DAY, now - timedelta(weeks=8)),
    ]


@pytest.mark.unit
def test_cache_expires_after_ttl() -> None:
    now = datetime(2025, 2, 1, tzinfo=timezone.utc)
    repository = StubStatsRepository()
    repository.global_data[StatsWindow.WEEK] = [
        _build_metric(now - timedelta(weeks=1), success=1, ingest_count=1)
    ]
    service = CachedStatsService(
        repository,
        global_ttl=timedelta(seconds=5),
        clock=lambda: now,
    )

    service.collect_global_stats(window=StatsWindow.WEEK, now=now)
    assert repository.global_calls == [
        (StatsWindow.WEEK, now - timedelta(weeks=8)),
    ]

    later = now + timedelta(seconds=6)
    repository.global_data[StatsWindow.WEEK] = [
        _build_metric(now - timedelta(weeks=1), success=2, ingest_count=2)
    ]
    refreshed = service.collect_global_stats(window=StatsWindow.WEEK, now=later)

    assert repository.global_calls == [
        (StatsWindow.WEEK, now - timedelta(weeks=8)),
        (StatsWindow.WEEK, later - timedelta(weeks=8)),
    ]
    assert refreshed.summary.success == 2


@pytest.mark.unit
def test_record_processing_event_invalidates_slot_and_global_cache() -> None:
    now = datetime(2025, 3, 1, tzinfo=timezone.utc)
    slot = Slot(
        id="slot-001",
        name="Slot 001",
        provider_id="gemini",
        operation_id="style_transfer",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    repository = StubStatsRepository()
    repository.global_data[StatsWindow.DAY] = [
        _build_metric(now - timedelta(days=1), success=1, ingest_count=1)
    ]
    repository.slot_data[(slot.id, StatsWindow.DAY)] = [
        _build_metric(now - timedelta(days=1), success=1, ingest_count=1)
    ]
    service = CachedStatsService(
        repository,
        slot_ttl=timedelta(seconds=60),
        global_ttl=timedelta(seconds=60),
        clock=lambda: now,
    )

    service.collect_global_stats(window=StatsWindow.DAY, now=now)
    service.collect_slot_stats(slot, window=StatsWindow.DAY, now=now)
    repository.global_calls.clear()
    repository.slot_calls.clear()

    log = ProcessingLog(
        id=uuid4(),
        job_id=uuid4(),
        slot_id=slot.id,
        status=ProcessingStatus.SUCCEEDED,
        occurred_at=now,
        message=None,
        details=None,
        provider_latency_ms=100,
    )
    service.record_processing_event(log)

    repository.global_data[StatsWindow.DAY] = [
        _build_metric(now, success=2, ingest_count=2)
    ]
    repository.slot_data[(slot.id, StatsWindow.DAY)] = [
        _build_metric(now, success=2, ingest_count=2)
    ]

    refreshed_global = service.collect_global_stats(
        window=StatsWindow.DAY, now=now + timedelta(seconds=1)
    )
    refreshed_slot = service.collect_slot_stats(
        slot, window=StatsWindow.DAY, now=now + timedelta(seconds=1)
    )

    assert repository.stored_logs == [log]
    assert repository.global_calls == [
        (StatsWindow.DAY, (now + timedelta(seconds=1)) - timedelta(weeks=8)),
    ]
    assert repository.slot_calls == [
        (slot.id, StatsWindow.DAY, (now + timedelta(seconds=1)) - timedelta(days=14)),
    ]
    assert refreshed_global.summary.success == 2
    assert refreshed_slot.summary.success == 2


@pytest.mark.unit
def test_record_processing_event_retries_before_propagating() -> None:
    now = datetime(2025, 3, 2, tzinfo=timezone.utc)
    repository = StubStatsRepository()
    repository.store_failures = 1
    service = CachedStatsService(
        repository,
        slot_ttl=timedelta(seconds=60),
        global_ttl=timedelta(seconds=60),
        clock=lambda: now,
        record_retry_delay=0.0,
    )
    log = ProcessingLog(
        id=uuid4(),
        job_id=uuid4(),
        slot_id="slot-retry",
        status=ProcessingStatus.SUCCEEDED,
        occurred_at=now,
        message=None,
        details=None,
        provider_latency_ms=10,
    )

    service.record_processing_event(log)

    assert repository.stored_logs == [log]


@pytest.mark.unit
def test_caches_are_keyed_by_since_parameter() -> None:
    now = datetime(2025, 4, 1, tzinfo=timezone.utc)
    repository = StubStatsRepository()
    repository.global_data[StatsWindow.DAY] = [
        _build_metric(now - timedelta(days=1), success=1, ingest_count=1)
    ]
    service = CachedStatsService(
        repository,
        global_ttl=timedelta(seconds=60),
        clock=lambda: now,
    )

    since = now - timedelta(days=7)
    aggregation_with_since = service.collect_global_stats(
        window=StatsWindow.DAY, since=since, now=now
    )
    aggregation_without_since = service.collect_global_stats(
        window=StatsWindow.DAY, now=now
    )

    assert aggregation_with_since is not aggregation_without_since
    assert repository.global_calls == [
        (StatsWindow.DAY, since),
        (StatsWindow.DAY, now - timedelta(weeks=8)),
    ]


@pytest.mark.unit
def test_distinct_cache_ttls_for_global_and_slot() -> None:
    now = datetime(2025, 5, 1, tzinfo=timezone.utc)
    slot = Slot(
        id="slot-123",
        name="Slot 123",
        provider_id="gemini",
        operation_id="style_transfer",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    repository = StubStatsRepository()
    repository.global_data[StatsWindow.WEEK] = [
        _build_metric(now - timedelta(weeks=1), success=1, ingest_count=1)
    ]
    repository.slot_data[(slot.id, StatsWindow.DAY)] = [
        _build_metric(now - timedelta(days=1), success=1, ingest_count=1)
    ]
    service = CachedStatsService(repository, clock=lambda: now)

    first_global = service.collect_global_stats(now=now)
    first_slot = service.collect_slot_stats(slot, now=now)

    repository.global_calls.clear()
    repository.slot_calls.clear()

    second_global = service.collect_global_stats(now=now + timedelta(seconds=59))
    second_slot = service.collect_slot_stats(slot, now=now + timedelta(minutes=2))

    assert second_global is first_global
    assert second_slot is first_slot
    assert repository.global_calls == []
    assert repository.slot_calls == []

    repository.global_data[StatsWindow.WEEK] = [
        _build_metric(now - timedelta(weeks=1), success=2, ingest_count=2)
    ]
    repository.slot_data[(slot.id, StatsWindow.DAY)] = [
        _build_metric(now - timedelta(days=1), success=2, ingest_count=2)
    ]

    third_global = service.collect_global_stats(now=now + timedelta(seconds=61))
    third_slot = service.collect_slot_stats(slot, now=now + timedelta(minutes=6))

    assert repository.global_calls == [
        (StatsWindow.WEEK, (now + timedelta(seconds=61)) - timedelta(weeks=8)),
    ]
    assert repository.slot_calls == [
        (slot.id, StatsWindow.DAY, (now + timedelta(minutes=6)) - timedelta(days=14)),
    ]
    assert third_global.summary.success == 2
    assert third_slot.summary.success == 2
    assert third_global is not first_global
    assert third_slot is not first_slot


@pytest.mark.unit
def test_recent_results_sorted_limited_and_cached() -> None:
    now = datetime(2025, 6, 1, tzinfo=timezone.utc)
    slot = Slot(
        id="slot-900",
        name="Slot 900",
        provider_id="gemini",
        operation_id="style_transfer",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    repository = StubStatsRepository()
    entries = []
    for offset in range(12):
        completed = now - timedelta(hours=offset)
        expires = completed + timedelta(hours=72)
        entries.append(
            _build_recent_result(
                job_id=uuid4(),
                completed_at=completed,
                expires_at=expires,
                size=offset,
            )
        )
    repository.recent_results_data[slot.id] = list(reversed(entries))
    service = CachedStatsService(repository, clock=lambda: now)

    first = service.recent_results(slot, now=now)

    assert len(first) == 10
    assert [item["completed_at"] for item in first] == [
        now - timedelta(hours=offset) for offset in range(10)
    ]
    assert repository.recent_results_calls == [
        (slot.id, now - timedelta(hours=72), 10, now)
    ]

    second = service.recent_results(slot, now=now + timedelta(minutes=4))
    assert second == first
    assert repository.recent_results_calls == [
        (slot.id, now - timedelta(hours=72), 10, now)
    ]


@pytest.mark.unit

def test_record_processing_event_invalidates_recent_results_cache() -> None:
    now = datetime(2025, 6, 3, tzinfo=timezone.utc)
    slot = Slot(
        id="slot-902",
        name="Slot 902",
        provider_id="gemini",
        operation_id="style_transfer",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    repository = StubStatsRepository()
    first_result = _build_recent_result(
        job_id=uuid4(),
        completed_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=71),
    )
    repository.recent_results_data[slot.id] = [first_result]
    service = CachedStatsService(repository, clock=lambda: now)

    initial = service.recent_results(slot, now=now)
    assert [item["job_id"] for item in initial] == [first_result["job_id"]]

    second_result = _build_recent_result(
        job_id=uuid4(),
        completed_at=now,
        expires_at=now + timedelta(hours=72),
    )
    repository.recent_results_data[slot.id] = [second_result]

    log = ProcessingLog(
        id=uuid4(),
        job_id=uuid4(),
        slot_id=slot.id,
        status=ProcessingStatus.SUCCEEDED,
        occurred_at=now,
    )
    service.record_processing_event(log)

    refreshed = service.recent_results(slot, now=now + timedelta(minutes=1))
    assert [item["job_id"] for item in refreshed] == [second_result["job_id"]]
    assert repository.recent_results_calls == [
        (slot.id, now - timedelta(hours=72), 10, now),
        (
            slot.id,
            (now + timedelta(minutes=1)) - timedelta(hours=72),
            10,
            now + timedelta(minutes=1),
        ),
    ]


@pytest.mark.unit

def test_recent_results_expire_after_retention_window() -> None:
    now = datetime(2025, 6, 2, tzinfo=timezone.utc)
    slot = Slot(
        id="slot-901",
        name="Slot 901",
        provider_id="gemini",
        operation_id="style_transfer",
        settings_json={},
        created_at=now,
        updated_at=now,
    )
    repository = StubStatsRepository()
    fresh = _build_recent_result(
        job_id=uuid4(),
        completed_at=now - timedelta(hours=1),
        expires_at=now + timedelta(hours=71),
    )
    expired = _build_recent_result(
        job_id=uuid4(),
        completed_at=now - timedelta(hours=80),
        expires_at=now - timedelta(hours=1),
    )
    repository.recent_results_data[slot.id] = [expired, fresh]
    service = CachedStatsService(repository, clock=lambda: now)

    current = service.recent_results(slot, now=now)
    assert [item["job_id"] for item in current] == [fresh["job_id"]]

    future_time = now + timedelta(hours=73)
    later = service.recent_results(slot, now=future_time)
    assert later == []
    assert repository.recent_results_calls == [
        (slot.id, now - timedelta(hours=72), 10, now),
        (slot.id, future_time - timedelta(hours=72), 10, future_time),
    ]
