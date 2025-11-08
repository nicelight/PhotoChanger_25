"""Persistence layer for job history."""

from __future__ import annotations

from dataclasses import dataclass
from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from ..db.db_models import JobHistoryModel


@dataclass(slots=True)
class JobHistoryRecord:
    """Lightweight view of job history used for public result serving."""

    job_id: str
    slot_id: str
    source: str
    status: str
    failure_reason: str | None
    result_path: str | None
    result_expires_at: datetime | None


class JobHistoryRepository:
    """Manage job_history records."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def create_pending(
        self,
        *,
        job_id: str,
        slot_id: str,
        started_at: datetime,
        sync_deadline: datetime,
        source: str = "ingest",
    ) -> None:
        with self._session_factory() as session:
            session.add(
                JobHistoryModel(
                    job_id=job_id,
                    slot_id=slot_id,
                    source=source,
                    status="pending",
                    started_at=started_at,
                    sync_deadline=sync_deadline,
                )
            )
            session.commit()

    def set_result(
        self,
        *,
        job_id: str,
        status: str,
        result_path: str,
        result_expires_at: datetime,
    ) -> None:
        with self._session_factory() as session:
            model = session.get(JobHistoryModel, job_id)
            if model is None:
                raise KeyError(f"Job '{job_id}' not found")
            model.status = status
            model.result_path = result_path
            model.result_expires_at = result_expires_at
            model.completed_at = datetime.utcnow()
            model.failure_reason = None
            session.commit()

    def set_failure(
        self,
        *,
        job_id: str,
        status: str,
        failure_reason: str,
    ) -> None:
        with self._session_factory() as session:
            model = session.get(JobHistoryModel, job_id)
            if model is None:
                raise KeyError(f"Job '{job_id}' not found")
            model.status = status
            model.failure_reason = failure_reason
            model.completed_at = datetime.utcnow()
            session.commit()

    def get_job(self, job_id: str) -> JobHistoryRecord:
        """Return a snapshot of job history for the given identifier."""
        with self._session_factory() as session:
            model = session.get(JobHistoryModel, job_id)
            if model is None:
                raise KeyError(f"Job '{job_id}' not found")
            return JobHistoryRecord(
                job_id=model.job_id,
                slot_id=model.slot_id,
                source=model.source,
                status=model.status,
                failure_reason=model.failure_reason,
                result_path=model.result_path,
                result_expires_at=model.result_expires_at,
            )
