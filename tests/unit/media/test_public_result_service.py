from datetime import datetime, timedelta
from pathlib import Path

import pytest
from src.app.media.public_result_service import PublicResultService
from src.app.repositories.job_history_repository import JobHistoryRecord


class DummyJobRepo:
    def __init__(self, record_map: dict[str, JobHistoryRecord]):
        self._records = record_map

    def get_job(self, job_id: str) -> JobHistoryRecord:
        try:
            return self._records[job_id]
        except KeyError:
            raise KeyError(job_id)


def make_record(tmp_path: Path, *, expires_delta: timedelta) -> JobHistoryRecord:
    result_file = tmp_path / "results" / "slot-001" / "job123" / "payload.png"
    result_file.parent.mkdir(parents=True, exist_ok=True)
    result_file.write_bytes(b"image-bytes")
    return JobHistoryRecord(
        job_id="job123",
        slot_id="slot-001",
        source="ingest",
        status="done",
        failure_reason=None,
        result_path=str(result_file),
        result_expires_at=datetime.utcnow() + expires_delta,
    )


def test_public_result_service_success(tmp_path: Path) -> None:
    record = make_record(tmp_path, expires_delta=timedelta(hours=1))
    service = PublicResultService(job_repo=DummyJobRepo({"job123": record}))

    response = service.open_result("job123")

    assert response.status_code == 200
    assert response.headers["content-disposition"].startswith("attachment;")
    assert response.media_type == "image/png"


def test_public_result_service_missing_job(tmp_path: Path) -> None:
    service = PublicResultService(job_repo=DummyJobRepo({}))

    response = service.open_result("missing")

    assert response.status_code == 404
    assert response.body == b'{"status":"error","failure_reason":"result_not_found"}'


def test_public_result_service_not_done(tmp_path: Path) -> None:
    record = make_record(tmp_path, expires_delta=timedelta(hours=1))
    record.status = "pending"
    service = PublicResultService(job_repo=DummyJobRepo({"job123": record}))

    response = service.open_result("job123")

    assert response.status_code == 404
    assert response.body == b'{"status":"error","failure_reason":"result_not_found"}'


def test_public_result_service_expired(tmp_path: Path) -> None:
    record = make_record(tmp_path, expires_delta=timedelta(hours=-1))
    service = PublicResultService(job_repo=DummyJobRepo({"job123": record}))

    response = service.open_result("job123")

    assert response.status_code == 410
    assert response.body == b'{"status":"error","failure_reason":"result_expired"}'


def test_public_result_service_missing_file(tmp_path: Path) -> None:
    record = make_record(tmp_path, expires_delta=timedelta(hours=1))
    Path(record.result_path).unlink()
    service = PublicResultService(job_repo=DummyJobRepo({"job123": record}))

    response = service.open_result("job123")

    assert response.status_code == 410
    assert response.body == b'{"status":"error","failure_reason":"result_expired"}'
