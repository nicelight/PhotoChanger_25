import sys
from datetime import datetime
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:  # pragma: no cover
    sys.path.append(str(ROOT))

from src.app.settings.settings_api import router


class DummySettingsService:
    def __init__(self) -> None:
        now = datetime(2025, 11, 9, 10, 0, 0)
        self.snapshot: dict[str, Any] = {
            "sync_response_seconds": 48,
            "result_ttl_hours": 72,
            "ingest_password_rotated_at": now,
            "ingest_password_rotated_by": "serg",
            "provider_keys": {"gemini": {"configured": True, "updated_at": now}},
        }
        self.last_payload: dict[str, Any] | None = None

    def load(self) -> dict[str, Any]:
        return self.snapshot

    def update(self, payload: dict[str, Any], actor: str | None = None) -> dict[str, Any]:
        self.last_payload = payload
        self.snapshot["sync_response_seconds"] = payload.get("sync_response_seconds", self.snapshot["sync_response_seconds"])
        return self.snapshot


def build_client(service: DummySettingsService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.settings_service = service
    return TestClient(app)


def test_read_settings_returns_snapshot() -> None:
    service = DummySettingsService()
    client = build_client(service)

    response = client.get("/api/settings")

    assert response.status_code == 200
    data = response.json()
    assert data["sync_response_seconds"] == 48
    assert data["provider_keys"]["gemini"]["configured"] is True


def test_update_settings_passes_payload_to_service() -> None:
    service = DummySettingsService()
    client = build_client(service)

    response = client.put("/api/settings", json={"sync_response_seconds": 42})

    assert response.status_code == 200
    assert service.last_payload == {"sync_response_seconds": 42}
