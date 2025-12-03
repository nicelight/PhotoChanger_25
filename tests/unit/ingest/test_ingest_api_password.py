from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.ingest.ingest_api import router


class DummyJob:
    def __init__(self, slot_id: str) -> None:
        self.slot_id = slot_id
        self.metadata: dict[str, str] = {}
        self.upload = None


class DummyIngestService:
    def __init__(self, ingest_password: str) -> None:
        self.ingest_password = ingest_password
        self.last_job: DummyJob | None = None
        self._lock = None

    def slot_lock(self, slot_id: str):
        import asyncio

        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    def verify_ingest_password(self, provided: str) -> bool:
        return provided == self.ingest_password

    def prepare_job(self, slot_id: str) -> DummyJob:
        job = DummyJob(slot_id)
        self.last_job = job
        return job

    async def validate_upload(self, job: DummyJob, upload, expected_hash: str):
        job.upload = upload
        return {"status": "ok"}

    async def process(self, job: DummyJob) -> bytes:
        job.metadata["result_content_type"] = "image/png"
        return b"processed"


def build_client(service: DummyIngestService) -> TestClient:
    app = FastAPI()
    app.state.ingest_service = service
    app.include_router(router)
    return TestClient(app)


def test_ingest_rejects_invalid_password(tmp_path) -> None:
    service = DummyIngestService(ingest_password="secret")
    client = build_client(service)

    response = client.post(
        "/api/ingest/slot-001",
        data={"password": "wrong", "hash_hex": "deadbeef"},
        files={"file": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 401
    body = response.json()
    assert body["detail"]["failure_reason"] == "invalid_password"


def test_ingest_accepts_valid_password(tmp_path) -> None:
    service = DummyIngestService(ingest_password="secret")
    client = build_client(service)

    response = client.post(
        "/api/ingest/slot-001",
        data={"password": "secret", "hash_hex": "deadbeef"},
        files={"file": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 200
    assert response.content == b"processed"
    assert response.headers["content-type"].startswith("image/png")
    assert service.last_job is not None
    assert service.last_job.metadata.get("ingest_password") == "secret"


def test_ingest_accepts_legacy_field_names(tmp_path) -> None:
    service = DummyIngestService(ingest_password="secret")
    client = build_client(service)

    response = client.post(
        "/api/ingest/slot-001",
        data={"password": "secret", "hash": "deadbeef"},
        files={"fileToUpload": ("file.png", b"data", "image/png")},
    )

    assert response.status_code == 200
    assert response.content == b"processed"
