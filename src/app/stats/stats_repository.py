"""Database aggregations for statistics."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from datetime import datetime

from sqlalchemy import func, nullslast
from sqlalchemy.orm import Session

from ..db.db_models import JobHistoryModel, SlotModel
from ..ingest.ingest_models import FailureReason, JobStatus


class StatsRepository:
    """Collect statistics from job_history and slots tables."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def system_metrics(self, window_start: datetime) -> dict[str, Any]:
        with self._session_factory() as session:
            total_jobs = session.query(func.count(JobHistoryModel.job_id)).scalar() or 0

            jobs_last_window = (
                session.query(func.count(JobHistoryModel.job_id))
                .filter(JobHistoryModel.started_at >= window_start)
                .scalar()
                or 0
            )

            timeouts_last_window = (
                session.query(func.count(JobHistoryModel.job_id))
                .filter(
                    JobHistoryModel.status == JobStatus.TIMEOUT.value,
                    JobHistoryModel.completed_at >= window_start,
                )
                .scalar()
                or 0
            )

            provider_errors_last_window = (
                session.query(func.count(JobHistoryModel.job_id))
                .filter(
                    JobHistoryModel.failure_reason == FailureReason.PROVIDER_ERROR.value,
                    JobHistoryModel.completed_at >= window_start,
                )
                .scalar()
                or 0
            )

        return {
            "jobs_total": total_jobs,
            "jobs_last_window": jobs_last_window,
            "timeouts_last_window": timeouts_last_window,
            "provider_errors_last_window": provider_errors_last_window,
        }

    def slot_metrics(self, window_start: datetime) -> Sequence[dict[str, Any]]:
        with self._session_factory() as session:
            slots = session.query(SlotModel).order_by(SlotModel.id).all()
            metrics: list[dict[str, Any]] = []
            for slot in slots:
                slot_id = slot.id
                jobs_last_window = self._count_jobs(session, slot_id, window_start)
                timeouts_last_window = self._count_timeouts(session, slot_id, window_start)
                provider_errors_last_window = self._count_provider_errors(session, slot_id, window_start)
                success_last_window = self._count_success(session, slot_id, window_start)

                last_success = (
                    session.query(JobHistoryModel)
                    .filter(JobHistoryModel.slot_id == slot_id, JobHistoryModel.status == JobStatus.DONE.value)
                    .order_by(nullslast(JobHistoryModel.completed_at.desc()))
                    .first()
                )
                last_error = (
                    session.query(JobHistoryModel)
                    .filter(
                        JobHistoryModel.slot_id == slot_id,
                        JobHistoryModel.failure_reason.isnot(None),
                    )
                    .order_by(
                        nullslast(JobHistoryModel.completed_at.desc()),
                        JobHistoryModel.started_at.desc(),
                    )
                    .first()
                )

                metrics.append(
                    {
                        "slot_id": slot_id,
                        "display_name": slot.display_name or slot_id,
                        "is_active": slot.is_active,
                        "jobs_last_window": jobs_last_window,
                        "timeouts_last_window": timeouts_last_window,
                        "provider_errors_last_window": provider_errors_last_window,
                        "success_last_window": success_last_window,
                        "last_success_at": (last_success.completed_at if last_success else None),
                        "last_error_reason": last_error.failure_reason if last_error else None,
                    }
                )
        return metrics

    @staticmethod
    def _count_jobs(session: Session, slot_id: str, window_start: datetime) -> int:
        return (
            session.query(func.count(JobHistoryModel.job_id))
            .filter(JobHistoryModel.slot_id == slot_id, JobHistoryModel.started_at >= window_start)
            .scalar()
            or 0
        )

    @staticmethod
    def _count_timeouts(session: Session, slot_id: str, window_start: datetime) -> int:
        return (
            session.query(func.count(JobHistoryModel.job_id))
            .filter(
                JobHistoryModel.slot_id == slot_id,
                JobHistoryModel.status == JobStatus.TIMEOUT.value,
                JobHistoryModel.completed_at >= window_start,
            )
            .scalar()
            or 0
        )

    @staticmethod
    def _count_provider_errors(session: Session, slot_id: str, window_start: datetime) -> int:
        return (
            session.query(func.count(JobHistoryModel.job_id))
            .filter(
                JobHistoryModel.slot_id == slot_id,
                JobHistoryModel.failure_reason == FailureReason.PROVIDER_ERROR.value,
                JobHistoryModel.completed_at >= window_start,
            )
            .scalar()
            or 0
        )

    @staticmethod
    def _count_success(session: Session, slot_id: str, window_start: datetime) -> int:
        return (
            session.query(func.count(JobHistoryModel.job_id))
            .filter(
                JobHistoryModel.slot_id == slot_id,
                JobHistoryModel.status == JobStatus.DONE.value,
                JobHistoryModel.completed_at >= window_start,
            )
            .scalar()
            or 0
        )
