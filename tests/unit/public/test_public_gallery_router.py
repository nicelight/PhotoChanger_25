from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

from src.app.public.public_gallery_router import _build_latest, _build_recent
from src.app.repositories.job_history_repository import JobHistoryRecord


class DummyJobRepo:
    def __init__(self, records_by_slot: dict[str, list[JobHistoryRecord]]):
        self._records_by_slot = records_by_slot

    def list_recent_by_slot(self, slot_id: str, limit: int = 10) -> list[JobHistoryRecord]:
        return list(self._records_by_slot.get(slot_id, []))[:limit]


def _record(job_id: str, path: Path, *, expires_delta_hours: int = -24) -> JobHistoryRecord:
    now = datetime.utcnow()
    return JobHistoryRecord(
        job_id=job_id,
        slot_id="slot-001",
        source="ingest",
        status="done",
        failure_reason=None,
        result_path=str(path),
        result_expires_at=now + timedelta(hours=expires_delta_hours),
        completed_at=now,
        started_at=now,
    )


def test_build_recent_skips_missing_files_and_keeps_existing_even_if_expired(
    tmp_path: Path,
) -> None:
    existing = tmp_path / "results" / "slot-001" / "job-ok" / "payload.png"
    existing.parent.mkdir(parents=True, exist_ok=True)
    existing.write_bytes(b"ok")
    missing = tmp_path / "results" / "slot-001" / "job-missing" / "payload.png"

    repo = DummyJobRepo(
        {
            "slot-001": [
                _record("job-ok", existing, expires_delta_hours=-48),
                _record("job-missing", missing, expires_delta_hours=48),
            ]
        }
    )

    results = _build_recent(repo, "slot-001", limit=10)

    assert len(results) == 1
    assert results[0]["job_id"] == "job-ok"


def test_build_latest_returns_none_for_missing_file(tmp_path: Path) -> None:
    missing = tmp_path / "results" / "slot-001" / "job-missing" / "payload.png"
    repo = DummyJobRepo({"slot-001": [_record("job-missing", missing)]})

    latest = _build_latest(repo, "slot-001")

    assert latest is None
