import json
import sys
from pathlib import Path
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:  # pragma: no cover - test helper
    sys.path.append(str(ROOT))

from src.app.ingest.ingest_errors import ProviderTimeoutError
from src.app.ingest.ingest_models import JobContext
from src.app.slots.slots_api import router


class DummyIngestService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []

    async def run_test_job(
        self,
        slot_id: str,
        upload,
        *,
        overrides: dict[str, Any] | None = None,
        expected_hash: str | None = None,
    ) -> tuple[JobContext, float]:
        if slot_id == "missing":
            raise KeyError(slot_id)
        if overrides and overrides.get("settings", {}).get("prompt") == "timeout":
            raise ProviderTimeoutError("timeout")
        job = JobContext(slot_id=slot_id, job_id="job-123")
        self.calls.append({"slot_id": slot_id, "overrides": overrides, "filename": upload.filename})
        return job, 1.23


def build_client(service: DummyIngestService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.ingest_service = service
    return TestClient(app)


def test_test_run_success_with_slot_payload_overrides() -> None:
    service = DummyIngestService()
    client = build_client(service)

    slot_payload = {
        "provider": "gemini",
        "settings": {"prompt": "Custom prompt"},
        "template_media": [{"media_kind": "style", "media_object_id": "media-1"}],
    }

    response = client.post(
        "/api/slots/slot-001/test-run",
        data={
            "slot_payload": json.dumps(slot_payload),
        },
        files={"test_image": ("test.jpg", b"123", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-123"
    assert payload["public_result_url"].endswith("/job-123")
    assert payload["completed_in_seconds"] == 1.23
    assert service.calls[0]["overrides"]["settings"]["prompt"] == "Custom prompt"
    assert service.calls[0]["overrides"]["template_media"][0]["media_object_id"] == "media-1"


def test_test_run_invalid_slot_payload_returns_400() -> None:
    service = DummyIngestService()
    client = build_client(service)

    response = client.post(
        "/api/slots/slot-001/test-run",
        data={"slot_payload": "not-json"},
        files={"test_image": ("test.jpg", b"123", "image/jpeg")},
    )

    assert response.status_code == 400
    assert response.json()["detail"]["failure_reason"] == "invalid_request"


def test_test_run_slot_not_found_returns_404() -> None:
    service = DummyIngestService()
    client = build_client(service)

    response = client.post(
        "/api/slots/missing/test-run",
        files={"test_image": ("test.jpg", b"123", "image/jpeg")},
    )

    assert response.status_code == 404


def test_test_run_provider_timeout_returns_504() -> None:
    service = DummyIngestService()
    client = build_client(service)

    response = client.post(
        "/api/slots/slot-001/test-run",
        data={"slot_payload": json.dumps({"settings": {"prompt": "timeout"}})},
        files={"test_image": ("test.jpg", b"123", "image/jpeg")},
    )

    assert response.status_code == 504
