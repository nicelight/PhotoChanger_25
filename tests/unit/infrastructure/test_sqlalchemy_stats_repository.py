from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Mapping
from uuid import uuid4

import pytest

_sqlalchemy = pytest.importorskip("sqlalchemy")
import sqlalchemy as sa

from src.app.domain.models import (
    JobFailureReason,
    ProcessingLog,
    ProcessingStatus,
)
from src.app.infrastructure.queue.schema import jobs, metadata as queue_metadata
from src.app.infrastructure.sqlalchemy.stats_repository import (
    SqlAlchemyStatsRepository,
    processing_log_aggregates,
)
from src.app.schemas.stats import StatsWindow


def _insert_job(conn: sa.Connection, *, job_id, slot_id: str, created_at: datetime) -> None:
    expires = created_at + timedelta(hours=1)
    conn.execute(
        sa.insert(jobs).values(
            id=job_id,
            slot_id=slot_id,
            status="pending",
            is_finalized=False,
            failure_reason=None,
            expires_at=expires,
            created_at=created_at,
            updated_at=created_at,
            finalized_at=None,
            payload_path=None,
            provider_job_reference=None,
            result_file_path=None,
            result_inline_base64=None,
            result_mime_type=None,
            result_size_bytes=None,
            result_checksum=None,
            result_expires_at=None,
        )
    )


def _select_aggregate(
    conn: sa.Connection, *, slot_id: str | None, granularity: str
) -> Mapping[str, object]:
    conditions: list[sa.ColumnElement[bool]] = [
        processing_log_aggregates.c.granularity == granularity,
    ]
    if slot_id is None:
        conditions.append(processing_log_aggregates.c.slot_id.is_(None))
    else:
        conditions.append(processing_log_aggregates.c.slot_id == slot_id)
    return (
        conn.execute(
            sa.select(processing_log_aggregates).where(*conditions)
        )
        .mappings()
        .one()
    )


@pytest.mark.unit
def test_store_processing_log_updates_aggregates() -> None:
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    queue_metadata.create_all(engine)
    processing_log_aggregates.metadata.create_all(engine)
    repository = SqlAlchemyStatsRepository(engine)

    slot_id = "slot-001"
    base_time = datetime(2025, 1, 1, 12, tzinfo=timezone.utc)

    with engine.begin() as conn:
        # Successful job
        job_success = uuid4()
        _insert_job(conn, job_id=job_success, slot_id=slot_id, created_at=base_time)

        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_success,
                slot_id=slot_id,
                status=ProcessingStatus.RECEIVED,
                occurred_at=base_time,
                message="received",
                details={"provider_id": "gemini"},
                provider_latency_ms=0,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_success,
                slot_id=slot_id,
                status=ProcessingStatus.SUCCEEDED,
                occurred_at=base_time + timedelta(minutes=1),
                message="provider replied",
                details={"provider_id": "gemini"},
                provider_latency_ms=50,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_success,
                slot_id=slot_id,
                status=ProcessingStatus.SUCCEEDED,
                occurred_at=base_time + timedelta(minutes=2),
                message="job finalized",
                details={
                    "result_file_path": "media/result.png",
                    "result_checksum": "abc",
                    "inline_preview": False,
                },
                provider_latency_ms=None,
            )
        )

        # Provider error job
        job_error = uuid4()
        _insert_job(
            conn,
            job_id=job_error,
            slot_id=slot_id,
            created_at=base_time + timedelta(minutes=5),
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_error,
                slot_id=slot_id,
                status=ProcessingStatus.RECEIVED,
                occurred_at=base_time + timedelta(minutes=5),
                message="received",
                details={"provider_id": "gemini"},
                provider_latency_ms=0,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_error,
                slot_id=slot_id,
                status=ProcessingStatus.FAILED,
                occurred_at=base_time + timedelta(minutes=6),
                message="provider failed",
                details={"provider_id": "gemini"},
                provider_latency_ms=100,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_error,
                slot_id=slot_id,
                status=ProcessingStatus.FAILED,
                occurred_at=base_time + timedelta(minutes=7),
                message="job failed",
                details={"failure_reason": JobFailureReason.PROVIDER_ERROR.value},
                provider_latency_ms=None,
            )
        )

        # Timeout job
        job_timeout = uuid4()
        _insert_job(
            conn,
            job_id=job_timeout,
            slot_id=slot_id,
            created_at=base_time + timedelta(minutes=10),
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_timeout,
                slot_id=slot_id,
                status=ProcessingStatus.RECEIVED,
                occurred_at=base_time + timedelta(minutes=10),
                message="received",
                details={"provider_id": "gemini"},
                provider_latency_ms=0,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_timeout,
                slot_id=slot_id,
                status=ProcessingStatus.TIMEOUT,
                occurred_at=base_time + timedelta(minutes=11),
                message="job timeout",
                details={"failure_reason": JobFailureReason.TIMEOUT.value},
                provider_latency_ms=None,
            )
        )


        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_timeout,
                slot_id=slot_id,
                status=ProcessingStatus.TIMEOUT,
                occurred_at=base_time + timedelta(minutes=12),
                message="deadline reached",
                details={"provider_id": "gemini"},
                provider_latency_ms=None,
            )
        )

        # Cancelled job
        job_cancelled = uuid4()
        _insert_job(
            conn,
            job_id=job_cancelled,
            slot_id=slot_id,
            created_at=base_time + timedelta(minutes=15),
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_cancelled,
                slot_id=slot_id,
                status=ProcessingStatus.RECEIVED,
                occurred_at=base_time + timedelta(minutes=15),
                message="received",
                details={"provider_id": "gemini"},
                provider_latency_ms=0,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_cancelled,
                slot_id=slot_id,
                status=ProcessingStatus.FAILED,
                occurred_at=base_time + timedelta(minutes=16),
                message="worker shutdown",
                details={"failure_reason": JobFailureReason.CANCELLED.value},
                provider_latency_ms=None,
            )
        )
        repository.store_processing_log(
            ProcessingLog(
                id=uuid4(),
                job_id=job_cancelled,
                slot_id=slot_id,
                status=ProcessingStatus.FAILED,
                occurred_at=base_time + timedelta(minutes=17),
                message="shutdown cleanup",
                details={},
                provider_latency_ms=None,
            )
        )

    with engine.connect() as conn:
        day_slot = _select_aggregate(conn, slot_id=slot_id, granularity="day")
        assert day_slot["success"] == 1
        assert day_slot["timeouts"] == 1
        assert day_slot["provider_errors"] == 1
        assert day_slot["cancelled"] == 1
        assert day_slot["errors"] == 0
        assert day_slot["ingest_count"] == 4

        day_global = _select_aggregate(conn, slot_id=None, granularity="day")
        assert day_global["success"] == 1
        assert day_global["timeouts"] == 1
        assert day_global["provider_errors"] == 1
        assert day_global["cancelled"] == 1
        assert day_global["errors"] == 0
        assert day_global["ingest_count"] == 4

        week_slot = _select_aggregate(conn, slot_id=slot_id, granularity="week")
        assert week_slot["success"] == 1
        assert week_slot["timeouts"] == 1
        assert week_slot["provider_errors"] == 1
        assert week_slot["cancelled"] == 1
        assert week_slot["errors"] == 0
        assert week_slot["ingest_count"] == 4


@pytest.mark.unit
def test_store_processing_log_updates_global_scope_with_null_slot_conflict() -> None:
    engine = sa.create_engine("sqlite:///:memory:", future=True)
    queue_metadata.create_all(engine)
    processing_log_aggregates.metadata.create_all(engine)
    repository = SqlAlchemyStatsRepository(engine)

    slot_id = "slot-aggregate"
    base_time = datetime(2025, 2, 2, 9, tzinfo=timezone.utc)

    with engine.begin() as conn:
        job_id = uuid4()
        _insert_job(conn, job_id=job_id, slot_id=slot_id, created_at=base_time)

    repository.store_processing_log(
        ProcessingLog(
            id=uuid4(),
            job_id=job_id,
            slot_id=slot_id,
            status=ProcessingStatus.RECEIVED,
            occurred_at=base_time,
            message="received",
            details={"provider_id": "gemini"},
            provider_latency_ms=0,
        )
    )
    repository.store_processing_log(
        ProcessingLog(
            id=uuid4(),
            job_id=job_id,
            slot_id=slot_id,
            status=ProcessingStatus.SUCCEEDED,
            occurred_at=base_time + timedelta(minutes=5),
            message="completed",
            details={
                "result_file_path": "media/result.png",
                "result_checksum": "checksum",
                "inline_preview": False,
            },
            provider_latency_ms=None,
        )
    )

    with engine.begin() as conn:
        rows = (
            conn.execute(
                sa.select(processing_log_aggregates)
                .where(
                    processing_log_aggregates.c.slot_id.is_(None),
                    processing_log_aggregates.c.granularity == StatsWindow.DAY.value,
                )
                .mappings()
                .all()
            )
        )

    assert len(rows) == 1
    aggregate = rows[0]
    assert aggregate["ingest_count"] == 1
    assert aggregate["success"] == 1

