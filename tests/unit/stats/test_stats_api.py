import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:  # pragma: no cover
    sys.path.append(str(ROOT))

from src.app.stats.stats_api import router


class DummyStatsService:
    def __init__(self) -> None:
        self.requests: list[int] = []

    def overview(self, window_minutes: int = 60) -> dict[str, Any]:
        self.requests.append(window_minutes)
        return {
            "window_minutes": window_minutes,
            "system": {"jobs_total": 1, "jobs_last_window": 1, "timeouts_last_window": 0, "provider_errors_last_window": 0, "storage_usage_mb": 0.0},
            "slots": [],
        }


def build_client(service: DummyStatsService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.stats_service = service
    return TestClient(app)


def test_stats_overview_uses_service() -> None:
    service = DummyStatsService()
    client = build_client(service)

    response = client.get("/api/stats/overview?window_minutes=15")

    assert response.status_code == 200
    assert response.json()["window_minutes"] == 15
    assert service.requests == [15]
