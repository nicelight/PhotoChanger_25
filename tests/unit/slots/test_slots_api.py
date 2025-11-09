

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, Sequence

from fastapi import FastAPI
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parents[3]
if str(ROOT) not in sys.path:  # pragma: no cover - test helper
    sys.path.append(str(ROOT))

from src.app.ingest.ingest_errors import ProviderTimeoutError
from src.app.ingest.ingest_models import JobContext
from src.app.ingest.ingest_service import UploadValidationResult
from src.app.repositories.job_history_repository import JobHistoryRecord
from src.app.slots.slots_api import router
from src.app.slots.slots_models import Slot, SlotTemplateMedia


class DummyIngestService:
    def __init__(self) -> None:
        self.calls: list[dict[str, Any]] = []
        self.sync_response_seconds = 48
        self.result_ttl_hours = 72

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
        job = JobContext(slot_id=slot_id, job_id="job-123", slot_settings={"prompt": "default"})
        job.metadata["source"] = "test"
        # Store overrides for test verification
        job._overrides = overrides or {}
        job._filename = getattr(upload, 'filename', 'test.jpg')
        return job, 1.23

    async def validate_upload(self, job: JobContext, upload, expected_hash: str | None) -> UploadValidationResult:
        job.slot_settings = {"prompt": "default"}
        return UploadValidationResult(content_type="image/jpeg", size_bytes=3, sha256="abc", filename="file.jpg")

    async def process(self, job: JobContext) -> bytes:
        if job.slot_settings.get("prompt") == "timeout":
            raise ProviderTimeoutError("timeout")
        # Store the call for test verification
        self.calls.append({
            "slot_id": job.slot_id, 
            "overrides": getattr(job, '_overrides', {}),
            "filename": getattr(job, '_filename', 'test.jpg')
        })
        return b"mock_result"


class DummySlotRepository:
    def __init__(self) -> None:
        self.slot = Slot(
            id="slot-001",
            provider="gemini",
            operation="image_edit",
            display_name="Slot 1",
            settings={"prompt": "Hi"},
            size_limit_mb=15,
            is_active=True,
            version=1,
            updated_by="serg",
            template_media=[
                SlotTemplateMedia(id="tmpl-1", slot_id="slot-001", media_kind="style", media_object_id="media-1")
            ],
            updated_at=datetime(2025, 11, 8, 10, 0, 0),
        )

    def list_slots(self) -> Sequence[Slot]:
        return [self.slot]

    def get_slot(self, slot_id: str) -> Slot:
        if slot_id != self.slot.id:
            raise KeyError(slot_id)
        return self.slot

    def update_slot(self, *_args, **kwargs) -> Slot:
        self.slot = Slot(
            id="slot-001",
            provider=kwargs["provider"],
            operation=kwargs["operation"],
            display_name=kwargs["display_name"],
            settings=kwargs["settings"],
            size_limit_mb=kwargs["size_limit_mb"],
            is_active=kwargs["is_active"],
            version=2,
            updated_by=kwargs.get("updated_by"),
            template_media=[
                SlotTemplateMedia(
                    id="tmpl-2",
                    slot_id="slot-001",
                    media_kind=item["media_kind"],
                    media_object_id=item["media_object_id"],
                )
                for item in kwargs["template_media"]
            ],
            updated_at=datetime(2025, 11, 8, 11, 0, 0),
        )
        return self.slot


class DummyJobRepo:
    def list_recent_by_slot(self, slot_id: str, limit: int = 10) -> Sequence[JobHistoryRecord]:
        base = datetime(2025, 11, 8, 12, 0, 0)
        return [
            JobHistoryRecord(
                job_id="job-1",
                slot_id=slot_id,
                source="ingest",
                status="done",
                failure_reason=None,
                result_path="media/results/slot-001/job-1/payload.png",
                result_expires_at=base + timedelta(hours=72),
                completed_at=base,
                started_at=base - timedelta(seconds=30),
            )
        ]


class DummySettingsService:
    def __init__(self, sync_seconds: int = 48, ttl_hours: int = 72) -> None:
        self._snapshot = {
            "sync_response_seconds": sync_seconds,
            "result_ttl_hours": ttl_hours,
            "ingest_password_rotated_at": None,
            "ingest_password_rotated_by": None,
            "provider_keys": {},
        }

    def snapshot(self) -> dict[str, Any]:
        return self._snapshot


def build_client(
    service: DummyIngestService,
    slot_repo: DummySlotRepository | None = None,
    job_repo: DummyJobRepo | None = None,
    settings_service: DummySettingsService | None = None,
) -> TestClient:
    app = FastAPI()
    app.include_router(router)
    app.state.ingest_service = service
    app.state.slot_repo = slot_repo or DummySlotRepository()
    app.state.job_repo = job_repo or DummyJobRepo()
    app.state.settings_service = settings_service or DummySettingsService()
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


def test_get_slots_returns_summaries() -> None:
    client = build_client(DummyIngestService())

    response = client.get("/api/slots")

    assert response.status_code == 200
    data = response.json()
    assert data[0]["slot_id"] == "slot-001"
    assert data[0]["version"] == 1


def test_get_slot_details_includes_recent_results() -> None:
    client = build_client(DummyIngestService())

    response = client.get("/api/slots/slot-001")

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Slot 1"
    assert payload["template_media"][0]["preview_url"].endswith("media-1")
    assert payload["recent_results"][0]["job_id"] == "job-1"


def test_update_slot_persists_changes() -> None:
    repo = DummySlotRepository()
    client = build_client(DummyIngestService(), slot_repo=repo)

    response = client.put(
        "/api/slots/slot-001",
        json={
            "display_name": "Renamed",
            "provider": "gemini",
            "operation": "image_edit",
            "is_active": False,
            "size_limit_mb": 18,
            "settings": {"prompt": "New"},
            "template_media": [{"media_kind": "style", "media_object_id": "media-2"}],
        },
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["display_name"] == "Renamed"
    assert payload["is_active"] is False
    assert payload["template_media"][0]["media_object_id"] == "media-2"
