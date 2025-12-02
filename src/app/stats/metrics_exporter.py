"""Prometheus metrics exporter without external dependencies."""

from __future__ import annotations

import os
import shutil
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Iterable, Sequence

from .stats_repository import StatsRepository

BUCKETS = [1, 5, 10, 20, 30, 40, 48, 60]


@dataclass(slots=True)
class SlotTotals:
    slot_id: str
    provider: str
    jobs_total: int
    timeouts_total: int
    provider_errors_total: int
    success_total: int


@dataclass(slots=True)
class DurationSample:
    slot_id: str
    provider: str
    seconds: float


@dataclass(slots=True)
class MetricsSnapshot:
    totals: Sequence[SlotTotals]
    durations: Sequence[DurationSample]
    media_usage_bytes: int
    media_capacity_bytes: int
    window_minutes: int
    sync_response_seconds: int


class MetricsExporter:
    """Collects statistics and renders them as Prometheus text format."""

    def __init__(
        self,
        stats_repo: StatsRepository,
        media_root: Path,
        sync_response_seconds: int,
    ) -> None:
        self._stats_repo = stats_repo
        self._media_root = media_root
        self._sync_response_seconds = sync_response_seconds

    def collect(self, window_minutes: int = 5) -> str:
        """Build metrics text for Prometheus scraping."""
        window_minutes = max(1, window_minutes)
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
        totals = [
            SlotTotals(
                slot_id=item["slot_id"],
                provider=item["provider"],
                jobs_total=int(item["jobs_total"]),
                timeouts_total=int(item["timeouts_total"]),
                provider_errors_total=int(item["provider_errors_total"]),
                success_total=int(item["success_total"]),
            )
            for item in self._stats_repo.slot_totals()
        ]
        durations = [
            DurationSample(
                slot_id=item["slot_id"],
                provider=item["provider"],
                seconds=float(item["seconds"]),
            )
            for item in self._stats_repo.slot_durations(window_start)
        ]
        usage_bytes, capacity_bytes = self._disk_usage()
        snapshot = MetricsSnapshot(
            totals=totals,
            durations=durations,
            media_usage_bytes=usage_bytes,
            media_capacity_bytes=capacity_bytes,
            window_minutes=window_minutes,
            sync_response_seconds=self._sync_response_seconds,
        )
        return format_prometheus(snapshot)

    def _disk_usage(self) -> tuple[int, int]:
        """Return (used_bytes, capacity_bytes) for media root."""
        try:
            stat = shutil.disk_usage(self._media_root)
            capacity = stat.total
        except OSError:
            return 0, 0
        return self._calc_usage_bytes(self._media_root), capacity

    @staticmethod
    def _calc_usage_bytes(root: Path) -> int:
        total = 0
        if root.exists():
            for dirpath, _, filenames in os.walk(root):
                for name in filenames:
                    try:
                        total += (Path(dirpath) / name).stat().st_size
                    except OSError:
                        continue
        return total


def format_prometheus(snapshot: MetricsSnapshot) -> str:
    """Render metrics snapshot into Prometheus text format."""
    lines: list[str] = []

    lines.append("# HELP ingest_requests_total Total ingest requests per slot/provider.")
    lines.append("# TYPE ingest_requests_total counter")
    for total in snapshot.totals:
        lines.append(
            f'ingest_requests_total{{slot_id="{total.slot_id}",provider="{total.provider}"}} {total.jobs_total}'
        )

    lines.append("# HELP ingest_success_total Successful ingest operations.")
    lines.append("# TYPE ingest_success_total counter")
    for total in snapshot.totals:
        lines.append(
            f'ingest_success_total{{slot_id="{total.slot_id}",provider="{total.provider}"}} {total.success_total}'
        )

    lines.append("# HELP ingest_timeout_total Ingest timeouts (HTTP 504).")
    lines.append("# TYPE ingest_timeout_total counter")
    for total in snapshot.totals:
        lines.append(
            f'ingest_timeout_total{{slot_id="{total.slot_id}",provider="{total.provider}"}} {total.timeouts_total}'
        )

    lines.append("# HELP ingest_provider_error_total Provider-side errors.")
    lines.append("# TYPE ingest_provider_error_total counter")
    for total in snapshot.totals:
        lines.append(
            f'ingest_provider_error_total{{slot_id="{total.slot_id}",provider="{total.provider}"}} {total.provider_errors_total}'
        )

    lines.extend(_format_histogram(snapshot.totals, snapshot.durations))

    lines.append("# HELP media_storage_bytes Current size of media/ directory (bytes).")
    lines.append("# TYPE media_storage_bytes gauge")
    lines.append(f"media_storage_bytes {snapshot.media_usage_bytes}")

    lines.append("# HELP media_disk_capacity_bytes Total disk capacity for media volume.")
    lines.append("# TYPE media_disk_capacity_bytes gauge")
    lines.append(f"media_disk_capacity_bytes {snapshot.media_capacity_bytes}")

    return "\n".join(lines) + "\n"


def _format_histogram(
    totals: Sequence[SlotTotals], durations: Sequence[DurationSample]
) -> Iterable[str]:
    """Render histogram buckets, sum and count for ingest duration."""
    lines: list[str] = []
    grouped: dict[tuple[str, str], list[float]] = defaultdict(list)
    for sample in durations:
        grouped[(sample.slot_id, sample.provider)].append(sample.seconds)

    # Ensure every slot/provider from totals has a histogram series, even without samples
    for total in totals:
        key = (total.slot_id, total.provider)
        samples_sorted = sorted(grouped.get(key, []))
        count = len(samples_sorted)
        idx = 0
        for bucket in BUCKETS:
            while idx < count and samples_sorted[idx] <= bucket:
                idx += 1
            lines.append(
                f'ingest_duration_seconds_bucket{{slot_id="{total.slot_id}",provider="{total.provider}",le="{bucket}"}} {idx}'
            )
        lines.append(
            f'ingest_duration_seconds_bucket{{slot_id="{total.slot_id}",provider="{total.provider}",le="+Inf"}} {count}'
        )
        lines.append(
            f'ingest_duration_seconds_sum{{slot_id="{total.slot_id}",provider="{total.provider}"}} {sum(samples_sorted):.6f}'
        )
        lines.append(
            f'ingest_duration_seconds_count{{slot_id="{total.slot_id}",provider="{total.provider}"}} {count}'
        )

    return lines
