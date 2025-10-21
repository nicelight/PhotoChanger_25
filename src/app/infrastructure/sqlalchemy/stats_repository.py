"""SQLAlchemy implementation of :class:`StatsRepository`."""

from __future__ import annotations

from datetime import datetime
from typing import Iterable, Mapping, Sequence

import sqlalchemy as sa
from sqlalchemy.engine import Engine

from ...domain.models import ProcessingLog, Slot, SlotRecentResult
from ...schemas.stats import StatsCounters, StatsMetric, StatsWindow
from ..queue.schema import jobs, processing_logs
from ..stats_repository import StatsRepository

_metadata = sa.MetaData()

processing_log_aggregates = sa.Table(
    "processing_log_aggregates",
    _metadata,
    sa.Column("id", sa.dialects.postgresql.UUID(as_uuid=True), primary_key=True),
    sa.Column("slot_id", sa.String(16), nullable=True),
    sa.Column("granularity", sa.String(8), nullable=False),
    sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
    sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
    sa.Column("success", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("timeouts", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column(
        "provider_errors", sa.Integer, nullable=False, server_default=sa.text("0")
    ),
    sa.Column("cancelled", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column("errors", sa.Integer, nullable=False, server_default=sa.text("0")),
    sa.Column(
        "ingest_count", sa.Integer, nullable=False, server_default=sa.text("0")
    ),
)


class SqlAlchemyStatsRepository(StatsRepository):
    """Load statistics and recent results using SQLAlchemy Core."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine

    def collect_global_metrics(
        self,
        *,
        window: StatsWindow,
        since: datetime | None = None,
    ) -> Iterable[StatsMetric]:
        return self._collect_metrics(slot_id=None, window=window, since=since)

    def collect_slot_metrics(
        self,
        slot: Slot,
        *,
        window: StatsWindow,
        since: datetime | None = None,
    ) -> Iterable[StatsMetric]:
        return self._collect_metrics(slot_id=slot.id, window=window, since=since)

    def store_processing_log(self, log: ProcessingLog) -> None:
        payload = {
            "id": log.id,
            "job_id": log.job_id,
            "slot_id": log.slot_id,
            "status": log.status.value,
            "occurred_at": log.occurred_at,
            "message": log.message,
            "details": dict(log.details) if log.details is not None else None,
            "provider_latency_ms": log.provider_latency_ms,
        }
        with self._engine.begin() as conn:
            conn.execute(sa.insert(processing_logs).values(payload))

    def load_recent_results(
        self,
        slot: Slot,
        *,
        since: datetime,
        limit: int,
        now: datetime,
    ) -> Iterable[SlotRecentResult]:
        if limit <= 0:
            return []
        stmt = (
            sa.select(
                jobs.c.id,
                jobs.c.finalized_at,
                jobs.c.result_expires_at,
                jobs.c.result_mime_type,
                jobs.c.result_file_path,
                jobs.c.result_size_bytes,
            )
            .where(
                jobs.c.slot_id == slot.id,
                jobs.c.is_finalized.is_(True),
                jobs.c.failure_reason.is_(None),
                jobs.c.finalized_at.is_not(None),
                jobs.c.result_file_path.is_not(None),
                jobs.c.result_mime_type.is_not(None),
                jobs.c.result_expires_at.is_not(None),
                jobs.c.finalized_at >= since,
                jobs.c.result_expires_at > now,
            )
            .order_by(jobs.c.finalized_at.desc())
            .limit(limit)
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        results: list[SlotRecentResult] = []
        for row in rows:
            finalized_at = row["finalized_at"]
            expires_at = row["result_expires_at"]
            if finalized_at is None or expires_at is None:
                continue
            path = str(row["result_file_path"])
            entry: SlotRecentResult = {
                "job_id": row["id"],
                "thumbnail_url": f"/media/{path}",
                "download_url": f"/public/results/{row['id']}",
                "completed_at": finalized_at,
                "result_expires_at": expires_at,
                "mime": row["result_mime_type"],
            }
            size = row.get("result_size_bytes")
            if size is not None:
                entry["size_bytes"] = size
            results.append(entry)
        return results

    def _collect_metrics(
        self,
        *,
        slot_id: str | None,
        window: StatsWindow,
        since: datetime | None,
    ) -> Sequence[StatsMetric]:
        conditions: list[sa.ColumnElement[bool]] = [
            processing_log_aggregates.c.granularity == window.value,
        ]
        if slot_id is None:
            conditions.append(processing_log_aggregates.c.slot_id.is_(None))
        else:
            conditions.append(processing_log_aggregates.c.slot_id == slot_id)
        if since is not None:
            conditions.append(processing_log_aggregates.c.period_end >= since)
        stmt = (
            sa.select(processing_log_aggregates)
            .where(*conditions)
            .order_by(processing_log_aggregates.c.period_start.asc())
        )
        with self._engine.connect() as conn:
            rows = conn.execute(stmt).mappings().all()
        return [self._row_to_metric(row) for row in rows]

    @staticmethod
    def _row_to_metric(row: Mapping[str, object]) -> StatsMetric:
        counters = StatsCounters(
            success=int(row.get("success", 0) or 0),
            timeouts=int(row.get("timeouts", 0) or 0),
            provider_errors=int(row.get("provider_errors", 0) or 0),
            cancelled=int(row.get("cancelled", 0) or 0),
            errors=int(row.get("errors", 0) or 0),
            ingest_count=int(row.get("ingest_count", 0) or 0),
        )
        return StatsMetric(
            period_start=row["period_start"],
            period_end=row["period_end"],
            counters=counters,
        )


__all__ = ["SqlAlchemyStatsRepository"]

