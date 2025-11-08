import sys
from datetime import datetime, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:  # pragma: no cover
    sys.path.append(str(ROOT))

from src.app.stats.stats_service import StatsService


class DummyRepo:
    def __init__(self) -> None:
        self.window = None

    def system_metrics(self, window_start: datetime) -> dict:
        self.window = window_start
        return {"jobs_total": 5, "jobs_last_window": 2, "timeouts_last_window": 1, "provider_errors_last_window": 0}

    def slot_metrics(self, window_start: datetime):
        return [
            {
                "slot_id": "slot-001",
                "display_name": "Slot 1",
                "is_active": True,
                "jobs_last_window": 2,
                "timeouts_last_window": 0,
                "provider_errors_last_window": 0,
                "last_success_at": datetime.utcnow(),
                "last_error_reason": None,
            }
        ]


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
    assert repo.window is not None
    assert repo.window > datetime.utcnow() - timedelta(minutes=31)
