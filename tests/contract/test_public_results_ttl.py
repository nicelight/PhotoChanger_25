from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.media.public_result_service import PublicResultService
from src.app.public.public_results_router import build_public_results_router
from src.app.repositories.job_history_repository import JobHistoryRecord


class RepoStub:
    def __init__(self, records: dict[str, JobHistoryRecord]):
        self._records = records

    def get_job(self, job_id: str) -> JobHistoryRecord:
        if job_id not in self._records:
            raise KeyError(job_id)
        return self._records[job_id]


def build_client(records: dict[str, JobHistoryRecord]) -> TestClient:
    service = PublicResultService(job_repo=RepoStub(records))
    app = FastAPI()
    app.include_router(build_public_results_router(service))
    return TestClient(app)


def test_public_results_contract_success(tmp_path: Path) -> None:
    payload = tmp_path / "results" / "slot01" / "job123" / "payload.jpg"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(b"jpeg-bytes")
    record = JobHistoryRecord(
        job_id="job123",
        slot_id="slot01",
        status="done",
        failure_reason=None,
        result_path=str(payload),
        result_expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    client = build_client({"job123": record})

    response = client.get("/public/results/job123")

    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.content == b"jpeg-bytes"


def test_public_results_contract_expired(tmp_path: Path) -> None:
    payload = tmp_path / "results" / "slot01" / "job999" / "payload.png"
    payload.parent.mkdir(parents=True, exist_ok=True)
    payload.write_bytes(b"png-bytes")
    record = JobHistoryRecord(
        job_id="job999",
        slot_id="slot01",
        status="done",
        failure_reason=None,
        result_path=str(payload),
        result_expires_at=datetime.utcnow() - timedelta(minutes=5),
    )
    client = build_client({"job999": record})

    response = client.get("/public/results/job999")

    assert response.status_code == 410
    assert response.json() == {"status": "error", "failure_reason": "result_expired"}
