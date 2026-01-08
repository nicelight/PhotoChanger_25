from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

from src.app.stats.stats_service import StatsService


class DummyRepo:
    def __init__(
        self,
        slot_metrics: list[dict] | None = None,
        recent_failures: list[dict] | None = None,
    ) -> None:
        self.window = None
        self._slot_metrics = slot_metrics or [
            {
                "slot_id": "slot-001",
                "display_name": "Slot 1",
                "is_active": True,
                "jobs_last_window": 2,
                "timeouts_last_window": 0,
                "provider_errors_last_window": 0,
                "failures_last_window": 0,
                "success_last_window": 2,
                "last_success_at": datetime.utcnow(),
                "last_error_reason": None,
            }
        ]
        self._recent_failures = recent_failures or []

    def system_metrics(self, window_start: datetime) -> dict:
        self.window = window_start
        return {
            "jobs_total": 5,
            "jobs_last_window": 2,
            "timeouts_last_window": 1,
            "provider_errors_last_window": 0,
        }

    def slot_metrics(self, window_start: datetime):
        self.window = window_start
        return self._slot_metrics

    def recent_failures(self, window_start: datetime, *, limit: int = 20, provider_only: bool = True):
        self.window = window_start
        return self._recent_failures


def test_overview_uses_repository_and_calculates_storage(tmp_path: Path) -> None:
    repo = DummyRepo()
    results_dir = tmp_path / "results"
    results_dir.mkdir()
    sample = results_dir / "file.bin"
    sample.write_bytes(b"x" * 1024 * 1024)  # 1 MB

    service = StatsService(repo=repo, media_paths=SimpleNamespace(results=results_dir))
    snapshot = service.overview(window_minutes=30)

    assert snapshot["window_minutes"] == 30
    assert snapshot["system"]["jobs_total"] == 5
    assert snapshot["system"]["storage_usage_mb"] == 1.0
    assert snapshot["slots"][0]["slot_id"] == "slot-001"
    assert snapshot["slots"][0]["success_last_window"] == 2
    assert repo.window is not None
    assert repo.window > datetime.utcnow() - timedelta(minutes=31)


def test_slot_stats_filters_inactive_and_adds_rates() -> None:
    now = datetime.utcnow()
    repo = DummyRepo(
        slot_metrics=[
            {
                "slot_id": "slot-001",
                "display_name": "Slot 1",
                "is_active": True,
                "jobs_last_window": 4,
                "timeouts_last_window": 1,
                "provider_errors_last_window": 0,
                "failures_last_window": 1,
                "success_last_window": 3,
                "last_success_at": now,
                "last_error_reason": None,
            },
            {
                "slot_id": "slot-002",
                "display_name": "Slot 2",
                "is_active": False,
                "jobs_last_window": 10,
                "timeouts_last_window": 2,
                "provider_errors_last_window": 1,
                "failures_last_window": 3,
                "success_last_window": 7,
                "last_success_at": now,
                "last_error_reason": "provider_error",
            },
        ]
    )

    service = StatsService(
        repo=repo, media_paths=SimpleNamespace(results=Path("/tmp/none"))
    )
    stats = service.slot_stats(window_minutes=15)

    assert stats["window_minutes"] == 15
    assert len(stats["slots"]) == 1
    slot = stats["slots"][0]
    assert slot["slot_id"] == "slot-001"
    assert slot["success_rate"] == pytest.approx(0.75)
    assert slot["timeout_rate"] == pytest.approx(0.25)


def test_slot_stats_includes_recent_failures() -> None:
    now = datetime.utcnow()
    repo = DummyRepo(
        recent_failures=[
            {
                "finished_at": now,
                "slot_id": "slot-001",
                "failure_reason": "provider_error",
            },
            {
                "finished_at": now,
                "slot_id": "slot-002",
                "failure_reason": "provider_timeout",
            },
        ]
    )
    service = StatsService(
        repo=repo, media_paths=SimpleNamespace(results=Path("/tmp/none"))
    )
    stats = service.slot_stats(window_minutes=10)

    assert stats["recent_failures"]
    assert stats["recent_failures"][0]["http_status"] == 502
    assert stats["recent_failures"][1]["http_status"] == 504
