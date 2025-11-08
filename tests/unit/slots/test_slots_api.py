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
from src.app.ingest.ingest_models import JobContext, UploadValidationResult
from src.app.slots.slots_api import router


class DummyIngestService:
    def __init__(self) -> None:
        self.last_job: JobContext | None = None
        self.failures: list[str] = []

    def prepare_job(self, slot_id: str, *, source: str = "ingest") -> JobContext:
        if slot_id == "missing":
            raise KeyError(slot_id)
        job = JobContext(slot_id=slot_id, job_id="job-123", slot_settings={"prompt": "default"})
        job.metadata["source"] = source
        return job

    async def validate_upload(self, job: JobContext, upload, expected_hash: str | None) -> UploadValidationResult:
        job.slot_settings = {"prompt": "default"}
        return UploadValidationResult(content_type="image/jpeg", size_bytes=3, sha256="abc", filename="file.jpg")

    async def process(self, job: JobContext) -> bytes:
        if job.slot_settings.get("prompt") == "timeout":
            raise ProviderTimeoutError("timeout")
        self.last_job = job
        return b"bytes"

    def record_failure(self, job: JobContext, failure_reason: Any, status=None) -> None:  # pragma: no cover - trivial
        self.failures.append(str(failure_reason))


def build_client(service: DummyIngestService) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.ingest_service = service
    return TestClient(app)


def test_test_run_success_overrides_prompt_and_templates() -> None:
    service = DummyIngestService()
    client = build_client(service)

    response = client.post(
        "/api/slots/slot-001/test-run",
        data={
            "prompt": "Custom prompt",
            "template_media": json.dumps([{"media_kind": "style", "media_object_id": "media-1"}]),
        },
        files={"test_image": ("test.jpg", b"123", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["job_id"] == "job-123"
    assert payload["public_result_url"].endswith("/job-123")
    assert service.last_job is not None
    assert service.last_job.slot_settings["prompt"] == "Custom prompt"
    assert service.last_job.slot_settings["template_media"][0]["media_object_id"] == "media-1"


def test_test_run_invalid_template_media_returns_400() -> None:
    service = DummyIngestService()
    client = build_client(service)

    response = client.post(
        "/api/slots/slot-001/test-run",
        data={"template_media": "not-json"},
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
        data={"prompt": "timeout"},
        files={"test_image": ("test.jpg", b"123", "image/jpeg")},
    )

    assert response.status_code == 504
