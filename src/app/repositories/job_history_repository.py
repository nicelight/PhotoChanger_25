"""Persistence layer for job history."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from ..db.db_models import JobHistoryModel


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
    ) -> None:
        with self._session_factory() as session:
            session.add(
                JobHistoryModel(
                    job_id=job_id,
                    slot_id=slot_id,
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
