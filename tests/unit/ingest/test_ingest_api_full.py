import asyncio
from typing import Any

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.ingest.ingest_api import router
from src.app.ingest.ingest_errors import (
    ProviderExecutionError,
    ProviderTimeoutError,
    SlotDisabledError,
)
from src.app.ingest.ingest_models import JobContext, UploadValidationResult


class StubIngestService:
    def __init__(self, *, raise_error: Exception | None = None) -> None:
        self.ingest_password = "secret"
        self.sync_response_seconds = 48
        self.result_ttl_hours = 72
        self._lock = asyncio.Lock()
        self.raise_error = raise_error
        self.last_job: JobContext | None = None

    def slot_lock(self, slot_id: str) -> asyncio.Lock:
        return self._lock

    def verify_ingest_password(self, provided: str) -> bool:
        return provided == self.ingest_password

    def prepare_job(self, slot_id: str, *, source: str = "ingest") -> JobContext:
        if slot_id == "missing":
            raise KeyError(slot_id)
        if slot_id == "disabled":
            raise SlotDisabledError(slot_id)
        job = JobContext(
            slot_id=slot_id,
            job_id="job-123",
            slot_settings={},
            slot_template_media={},
            slot_version=1,
        )
        job.metadata["provider"] = "gemini"
        self.last_job = job
        return job

    async def validate_upload(
        self, job: JobContext, upload: Any, expected_hash: str | None
    ) -> UploadValidationResult:
        job.upload = UploadValidationResult(
            content_type=upload.content_type or "image/png",
            size_bytes=3,
            sha256="abc",
            filename=upload.filename or "file.png",
        )
        return job.upload

    async def process(self, job: JobContext) -> bytes:
        if self.raise_error:
            err = self.raise_error
            self.raise_error = None
            raise err
        job.metadata["result_content_type"] = "image/png"
        return b"result-bytes"


def build_client(service: StubIngestService) -> TestClient:
    app = FastAPI()
    app.state.ingest_service = service
    app.include_router(router)
    return TestClient(app)


def test_ingest_returns_binary_response(tmp_path) -> None:
    service = StubIngestService()
    client = build_client(service)

    response = client.post(
        "/api/ingest/slot-001",
        data={"password": "secret", "hash_hex": "deadbeef"},
        files={"file": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 200
    assert response.headers["content-type"].startswith("image/png")
    assert response.content == b"result-bytes"
    assert service.last_job is not None


def test_ingest_slot_disabled_returns_404(tmp_path) -> None:
    service = StubIngestService()
    client = build_client(service)

    response = client.post(
        "/api/ingest/disabled",
        data={"password": "secret", "hash_hex": "deadbeef"},
        files={"file": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 404
    body = response.json()
    assert body["detail"]["failure_reason"] == "slot_disabled"


def test_ingest_rate_limited_when_slot_busy(tmp_path) -> None:
    service = StubIngestService()
    client = build_client(service)
    loop = asyncio.get_event_loop()
    loop.run_until_complete(service.slot_lock("slot-001").acquire())

    try:
        response = client.post(
            "/api/ingest/slot-001",
            data={"password": "secret", "hash_hex": "deadbeef"},
            files={"file": ("file.png", b"data", "image/png")},
        )
    finally:
        service.slot_lock("slot-001").release()

    assert response.status_code == 429
    body = response.json()
    assert body["detail"]["failure_reason"] == "rate_limited"


def test_ingest_timeout_maps_to_504(tmp_path) -> None:
    service = StubIngestService(raise_error=ProviderTimeoutError("timeout"))
    client = build_client(service)

    response = client.post(
        "/api/ingest/slot-001",
        data={"password": "secret", "hash_hex": "deadbeef"},
        files={"file": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 504
    body = response.json()
    assert body["detail"]["failure_reason"] == "provider_timeout"


def test_ingest_provider_error_maps_to_502(tmp_path) -> None:
    service = StubIngestService(raise_error=ProviderExecutionError("boom"))
    client = build_client(service)

    response = client.post(
        "/api/ingest/slot-001",
        data={"password": "secret", "hash_hex": "deadbeef"},
        files={"file": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 502
    body = response.json()
    assert body["detail"]["failure_reason"] == "provider_error"
    assert "boom" in body["detail"]["message"]
