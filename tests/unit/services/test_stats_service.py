from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.app.domain.models import ProcessingLog, ProcessingStatus, Slot
from src.app.schemas.stats import StatsCounters, StatsMetric, StatsWindow
from src.app.services.stats import CachedStatsService


class StubStatsRepository:
    def __init__(self) -> None:
        self.global_data: dict[StatsWindow, list[StatsMetric]] = {}
        self.slot_data: dict[tuple[str, StatsWindow], list[StatsMetric]] = {}
        self.global_calls: list[tuple[StatsWindow, datetime | None]] = []
        self.slot_calls: list[tuple[str, StatsWindow, datetime | None]] = []
        self.stored_logs: list[ProcessingLog] = []

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
        self.stored_logs.append(log)


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
def test_collect_global_stats_accepts_naive_since() -> None:
    now = datetime(2025, 1, 10, tzinfo=timezone.utc)
    naive_since = datetime(2024, 12, 31)
    repository = StubStatsRepository()
    service = CachedStatsService(
        repository,
        global_ttl=timedelta(seconds=0),
        clock=lambda: now,
    )

    service.collect_global_stats(window=StatsWindow.DAY, since=naive_since, now=now)

    assert repository.global_calls == [
        (StatsWindow.DAY, naive_since.replace(tzinfo=timezone.utc)),
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
