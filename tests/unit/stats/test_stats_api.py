from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.auth.auth_dependencies import require_admin_user
from src.app.stats.stats_api import router


class DummyStatsService:
    def __init__(self) -> None:
        self.overview_requests: list[int] = []
        self.slot_requests: list[int] = []

    def overview(self, window_minutes: int = 60) -> dict[str, Any]:
        self.overview_requests.append(window_minutes)
        return {
            "window_minutes": window_minutes,
            "system": {
                "jobs_total": 1,
                "jobs_last_window": 1,
                "timeouts_last_window": 0,
                "provider_errors_last_window": 0,
                "storage_usage_mb": 0.0,
            },
            "slots": [],
        }

    def slot_stats(self, window_minutes: int = 60) -> dict[str, Any]:
        self.slot_requests.append(window_minutes)
        return {
            "window_minutes": window_minutes,
            "slots": [
                {
                    "slot_id": "slot-001",
                    "display_name": "Slot 1",
                    "is_active": True,
                    "jobs_last_window": 2,
                    "timeouts_last_window": 0,
                    "provider_errors_last_window": 0,
                    "success_last_window": 2,
                    "success_rate": 1.0,
                    "timeout_rate": 0.0,
                }
            ],
        }


class DummyAuthService:
    def validate_token(
        self, token: str, required_scope: str | None = None
    ) -> dict[str, str]:
        return {"sub": "serg", "scope": "admin"}


def build_client(service: DummyStatsService, *, with_auth: bool = True) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.stats_service = service
    app.state.auth_service = DummyAuthService()
    if with_auth:
        app.dependency_overrides[require_admin_user] = lambda: {
            "sub": "serg",
            "scope": "admin",
        }
    return TestClient(app)


def test_stats_overview_uses_service() -> None:
    service = DummyStatsService()
    client = build_client(service)

    response = client.get("/api/stats/overview?window_minutes=15")

    assert response.status_code == 200
    assert response.json()["window_minutes"] == 15
    assert service.overview_requests == [15]


def test_stats_slots_uses_service() -> None:
    service = DummyStatsService()
    client = build_client(service)

    response = client.get("/api/stats/slots?window_minutes=30")

    assert response.status_code == 200
    payload = response.json()
    assert payload["window_minutes"] == 30
    assert len(payload["slots"]) == 1
    assert service.slot_requests == [30]


def test_stats_endpoints_require_authentication() -> None:
    service = DummyStatsService()
    client = build_client(service, with_auth=False)

    response = client.get("/api/stats/overview")

    assert response.status_code == 401
    assert response.json()["detail"]["failure_reason"] == "missing_token"
