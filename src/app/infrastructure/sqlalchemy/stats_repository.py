"""SQLAlchemy implementation of :class:`StatsRepository`."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping, Sequence
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.engine import Engine
from sqlalchemy.dialects.postgresql import insert as pg_insert

from ...domain.models import (
    JobFailureReason,
    ProcessingLog,
    ProcessingStatus,
    Slot,
    SlotRecentResult,
)
from ...schemas.stats import StatsCounters, StatsMetric, StatsWindow
from ..queue.schema import jobs, processing_logs
from ..stats_repository import StatsRepository

_metadata = sa.MetaData()

_GLOBAL_SCOPE_SENTINEL = "GLOBAL"

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
    sa.Column(
        "created_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    ),
    sa.Column(
        "updated_at",
        sa.DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        server_onupdate=sa.func.now(),
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
        counters = self._derive_counters(log)
        with self._engine.begin() as conn:
            conn.execute(sa.insert(processing_logs).values(payload))
            if any(counters.values()):
                self._update_aggregates(conn, log, counters)

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

    def _update_aggregates(
        self,
        conn: sa.Connection,
        log: ProcessingLog,
        counters: Mapping[str, int],
    ) -> None:
        occurred_at = self._as_utc(log.occurred_at)
        for window in StatsWindow:
            start, end = self._period_bounds(occurred_at, window)
            for scope in (None, log.slot_id):
                self._upsert_aggregate(
                    conn,
                    slot_id=scope,
                    granularity=window.value,
                    period_start=start,
                    period_end=end,
                    counters=counters,
                )

    def _upsert_aggregate(
        self,
        conn: sa.Connection,
        *,
        slot_id: str | None,
        granularity: str,
        period_start: datetime,
        period_end: datetime,
        counters: Mapping[str, int],
    ) -> None:
        insert_values = {
            "id": uuid4(),
            "slot_id": slot_id,
            "granularity": granularity,
            "period_start": period_start,
            "period_end": period_end,
            "success": counters["success"],
            "timeouts": counters["timeouts"],
            "provider_errors": counters["provider_errors"],
            "cancelled": counters["cancelled"],
            "errors": counters["errors"],
            "ingest_count": counters["ingest_count"],
        }
        insert_stmt = pg_insert(processing_log_aggregates).values(insert_values)
        excluded = insert_stmt.excluded
        coalesced_slot_id = sa.func.coalesce(
            processing_log_aggregates.c.slot_id,
            sa.literal_column(f"'{_GLOBAL_SCOPE_SENTINEL}'"),
        )
        conn.execute(
            insert_stmt.on_conflict_do_update(
                index_elements=[
                    coalesced_slot_id,
                    processing_log_aggregates.c.granularity,
                    processing_log_aggregates.c.period_start,
                    processing_log_aggregates.c.period_end,
                ],
                set_={
                    "success": processing_log_aggregates.c.success
                    + excluded.success,
                    "timeouts": processing_log_aggregates.c.timeouts
                    + excluded.timeouts,
                    "provider_errors": processing_log_aggregates.c.provider_errors
                    + excluded.provider_errors,
                    "cancelled": processing_log_aggregates.c.cancelled
                    + excluded.cancelled,
                    "errors": processing_log_aggregates.c.errors + excluded.errors,
                    "ingest_count": processing_log_aggregates.c.ingest_count
                    + excluded.ingest_count,
                    "updated_at": sa.func.now(),
                },
            )
        )

    @staticmethod
    def _as_utc(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    @staticmethod
    def _period_bounds(
        occurred_at: datetime, window: StatsWindow
    ) -> tuple[datetime, datetime]:
        if window is StatsWindow.DAY:
            start = occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
            end = start + timedelta(days=1)
            return start, end
        if window is StatsWindow.WEEK:
            day_start = occurred_at.replace(hour=0, minute=0, second=0, microsecond=0)
            start = day_start - timedelta(days=day_start.weekday())
            end = start + timedelta(days=7)
            return start, end
        raise ValueError(f"Unsupported stats window: {window}")

    @staticmethod
    def _derive_counters(log: ProcessingLog) -> dict[str, int]:
        counters = {
            "success": 0,
            "timeouts": 0,
            "provider_errors": 0,
            "cancelled": 0,
            "errors": 0,
            "ingest_count": 0,
        }

        details: Mapping[str, object] = {}
        if log.details is not None and isinstance(log.details, Mapping):
            details = dict(log.details)

        failure_reason_raw = details.get("failure_reason") if details else None
        failure_reason = (
            str(failure_reason_raw)
            if failure_reason_raw is not None
            else None
        )

        if log.status is ProcessingStatus.RECEIVED:
            counters["ingest_count"] = 1
            return counters

        if log.status is ProcessingStatus.SUCCEEDED:
            if {
                "result_file_path",
                "result_checksum",
                "inline_preview",
            } & details.keys():
                counters["success"] = 1
            return counters

        if log.status is ProcessingStatus.TIMEOUT:
            if failure_reason is not None:
                counters["timeouts"] = 1
            return counters

        if log.status is ProcessingStatus.FAILED:
            if failure_reason == JobFailureReason.CANCELLED.value:
                counters["cancelled"] = 1
            elif failure_reason == JobFailureReason.PROVIDER_ERROR.value:
                counters["provider_errors"] = 1
            elif failure_reason == JobFailureReason.TIMEOUT.value:
                counters["timeouts"] = 1
            elif failure_reason is not None:
                counters["errors"] = 1
            return counters

        return counters

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

