"""Statistics aggregation logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

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
