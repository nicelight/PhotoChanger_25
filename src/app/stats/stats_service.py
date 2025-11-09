"""Statistics aggregation logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import MediaPaths
from .stats_repository import StatsRepository


@dataclass(slots=True)
class StatsService:
    """Aggregate ingest statistics for admin UI."""

    repo: StatsRepository
    media_paths: MediaPaths

    def overview(self, window_minutes: int = 60) -> dict:
        """Return system + slot metrics for the requested time window."""
        window_minutes = max(1, window_minutes)
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
        system = self.repo.system_metrics(window_start)
        slots = self.repo.slot_metrics(window_start)
        system["storage_usage_mb"] = self._calc_storage_usage_mb(self.media_paths.results)
        return {
            "window_minutes": window_minutes,
            "system": system,
            "slots": slots,
        }

    def slot_stats(self, window_minutes: int = 60) -> dict[str, Any]:
        """Return per-slot metrics for active slots only."""
        window_minutes = max(1, window_minutes)
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
        raw_slots = self.repo.slot_metrics(window_start)
        active_slots = []
        for slot in raw_slots:
            if not slot.get("is_active"):
                continue
            active_slots.append(self._augment_slot_metrics(slot))
        return {
            "window_minutes": window_minutes,
            "slots": active_slots,
        }

    @staticmethod
    def _calc_storage_usage_mb(root: Path) -> float:
        total_bytes = 0
        if root.exists():
            for dirpath, _, filenames in os.walk(root):
                for filename in filenames:
                    try:
                        total_bytes += (Path(dirpath) / filename).stat().st_size
                    except OSError:
                        continue
        return round(total_bytes / (1024 * 1024), 2)

    @staticmethod
    def _augment_slot_metrics(slot: dict[str, Any]) -> dict[str, Any]:
        enriched = dict(slot)
        total_jobs_started = enriched.get("jobs_last_window", 0) or 0
        completed_jobs = enriched.get("completed_last_window")
        if completed_jobs is None:
            completed_jobs = total_jobs_started
        completed_jobs = completed_jobs or 0
        success = enriched.get("success_last_window", 0) or 0
        timeouts = enriched.get("timeouts_last_window", 0) or 0
        if completed_jobs > 0:
            enriched["success_rate"] = round(success / completed_jobs, 4)
            enriched["timeout_rate"] = round(timeouts / completed_jobs, 4)
        else:
            enriched["success_rate"] = 0.0
            enriched["timeout_rate"] = 0.0
        enriched["completed_last_window"] = completed_jobs
        enriched["jobs_last_window"] = total_jobs_started
        return enriched
