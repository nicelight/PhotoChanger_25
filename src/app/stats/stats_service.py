"""Statistics aggregation logic."""

from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

from ..config import MediaPaths
from ..ingest.ingest_models import FailureReason
from .stats_repository import StatsRepository

MAX_WINDOW_MINUTES = 4320


@dataclass(slots=True)
class StatsService:
    """Aggregate ingest statistics for admin UI."""

    repo: StatsRepository
    media_paths: MediaPaths

    def overview(self, window_minutes: int = 60) -> dict[str, Any]:
        """Return system + slot metrics for the requested time window."""
        window_minutes = max(1, min(window_minutes, MAX_WINDOW_MINUTES))
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
        system = self.repo.system_metrics(window_start)
        slots = self.repo.slot_metrics(window_start)
        system["storage_usage_mb"] = self._calc_storage_usage_mb(
            self.media_paths.results
        )
        return {
            "window_minutes": window_minutes,
            "system": system,
            "slots": slots,
        }

    def slot_stats(self, window_minutes: int = 60) -> dict[str, Any]:
        """Return per-slot metrics for active slots only."""
        window_minutes = max(1, min(window_minutes, MAX_WINDOW_MINUTES))
        window_start = datetime.utcnow() - timedelta(minutes=window_minutes)
        raw_slots = self.repo.slot_metrics(window_start)
        recent_failures = [
            {
                "finished_at": item.get("finished_at"),
                "slot_id": item.get("slot_id"),
                "failure_reason": item.get("failure_reason"),
                "http_status": self._failure_http_status(item.get("failure_reason")),
            }
            for item in self.repo.recent_failures(
                window_start, limit=20, provider_only=True
            )
        ]
        active_slots = []
        for slot in raw_slots:
            if not slot.get("is_active"):
                continue
            active_slots.append(self._augment_slot_metrics(slot))
        return {
            "window_minutes": window_minutes,
            "slots": active_slots,
            "recent_failures": recent_failures,
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
        total_jobs = enriched.get("jobs_last_window", 0) or 0
        success = enriched.get("success_last_window", 0) or 0
        timeouts = enriched.get("timeouts_last_window", 0) or 0
        if total_jobs > 0:
            enriched["success_rate"] = round(success / total_jobs, 4)
            enriched["timeout_rate"] = round(timeouts / total_jobs, 4)
        else:
            enriched["success_rate"] = 0.0
            enriched["timeout_rate"] = 0.0
        return enriched

    @staticmethod
    def _failure_http_status(reason: str | None) -> int:
        mapping = {
            FailureReason.INVALID_REQUEST.value: 400,
            FailureReason.INVALID_PASSWORD.value: 401,
            FailureReason.SLOT_NOT_FOUND.value: 404,
            FailureReason.SLOT_DISABLED.value: 404,
            FailureReason.PAYLOAD_TOO_LARGE.value: 413,
            FailureReason.UNSUPPORTED_MEDIA_TYPE.value: 415,
            FailureReason.RATE_LIMITED.value: 429,
            FailureReason.PROVIDER_ERROR.value: 502,
            FailureReason.PROVIDER_TIMEOUT.value: 504,
            FailureReason.INTERNAL_ERROR.value: 500,
        }
        if not reason:
            return 500
        return mapping.get(reason, 500)
