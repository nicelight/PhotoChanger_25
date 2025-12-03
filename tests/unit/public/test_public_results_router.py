from datetime import datetime, timedelta
from pathlib import Path

from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.app.media.public_result_service import PublicResultService
from src.app.public.public_results_router import build_public_results_router
from src.app.repositories.job_history_repository import JobHistoryRecord


class DummyJobRepo:
    def __init__(self, records: dict[str, JobHistoryRecord]):
        self._records = records

    def get_job(self, job_id: str) -> JobHistoryRecord:
        try:
            return self._records[job_id]
        except KeyError:
            raise KeyError(job_id)


def create_app(service: PublicResultService) -> TestClient:
    app = FastAPI()
    app.include_router(build_public_results_router(service))
    return TestClient(app)


def test_public_results_router_success(tmp_path: Path) -> None:
    result_file = tmp_path / "res" / "slot" / "job123" / "payload.jpg"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_bytes(b"jpeg-bytes")
    record = JobHistoryRecord(
        job_id="job123",
        slot_id="slot",
        source="ingest",
        status="done",
        failure_reason=None,
        result_path=str(result_file),
        result_expires_at=datetime.utcnow() + timedelta(hours=1),
    )
    client = create_app(PublicResultService(job_repo=DummyJobRepo({"job123": record})))

    response = client.get("/public/results/job123")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("inline;")
    assert response.content == b"jpeg-bytes"


def test_public_results_router_expired(tmp_path: Path) -> None:
    result_file = tmp_path / "res" / "slot" / "job123" / "payload.png"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_bytes(b"png-bytes")
    record = JobHistoryRecord(
        job_id="job123",
        slot_id="slot",
        source="ingest",
        status="done",
        failure_reason=None,
        result_path=str(result_file),
        result_expires_at=datetime.utcnow() - timedelta(hours=1),
    )
    client = create_app(PublicResultService(job_repo=DummyJobRepo({"job123": record})))

    response = client.get("/public/results/job123")

    assert response.status_code == 410
    assert response.json() == {"status": "error", "failure_reason": "result_expired"}


def test_public_results_router_not_found(tmp_path: Path) -> None:
    client = create_app(PublicResultService(job_repo=DummyJobRepo({})))

    response = client.get("/public/results/missing")

    assert response.status_code == 404
    assert response.json() == {"status": "error", "failure_reason": "result_not_found"}
