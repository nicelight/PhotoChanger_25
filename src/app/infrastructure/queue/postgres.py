"""PostgreSQL-backed queue repository with optional SQLite fallback for tests."""

from __future__ import annotations

import json
import sqlite3
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Iterator
from uuid import UUID

from ...domain.models import (
    Job,
    JobFailureReason,
    JobStatus,
    ProcessingLog,
    ProcessingStatus,
)
from ..job_repository import JobRepository
from ...services.job_service import QueueBusyError, QueueUnavailableError

try:  # pragma: no cover - optional dependency
    import psycopg
    from psycopg.rows import dict_row
except Exception:  # pragma: no cover - fall back when psycopg missing
    psycopg = None  # type: ignore[assignment]
    dict_row = None  # type: ignore[assignment]


@dataclass(slots=True)
class PostgresQueueConfig:
    """Configuration required to talk to the queue database."""

    dsn: str
    poll_interval_seconds: float = 1.0
    max_batch_size: int = 1
    statement_timeout_ms: int = 5_000
    max_in_flight_jobs: int | None = None


class PostgresJobQueue(JobRepository):
    """Concrete repository backed by PostgreSQL with a SQLite test fallback."""

    def __init__(self, *, config: PostgresQueueConfig) -> None:
        self.config = config
        if self._is_sqlite_dsn(config.dsn):
            self._backend: _QueueBackend = _SQLiteQueueBackend(config)
        else:
            self._backend = _PostgresQueueBackend(config)

    # Public API ---------------------------------------------------------

    def enqueue(self, job: Job) -> Job:  # type: ignore[override]
        return self._backend.enqueue(job)

    def acquire_for_processing(self, *, now: datetime) -> Job | None:  # type: ignore[override]
        return self._backend.acquire_for_processing(now=now)

    def mark_finalized(self, job: Job) -> Job:  # type: ignore[override]
        return self._backend.mark_finalized(job)

    def release_expired(self, *, now: datetime) -> Iterable[Job]:  # type: ignore[override]
        return self._backend.release_expired(now=now)

    def append_processing_logs(self, logs: Iterable[ProcessingLog]) -> None:
        self._backend.append_processing_logs(logs)

    def list_processing_logs(self, job_id: UUID) -> list[ProcessingLog]:
        """Return processing logs ordered by ``occurred_at`` for debugging/tests."""

        return self._backend.list_processing_logs(job_id)

    # Helpers ------------------------------------------------------------

    @staticmethod
    def _is_sqlite_dsn(dsn: str) -> bool:
        return dsn == ":memory:" or dsn.startswith("sqlite://") or dsn.startswith("file:")


class _QueueBackend:
    """Backend protocol implemented by concrete database adapters."""

    def enqueue(self, job: Job) -> Job:
        raise NotImplementedError

    def acquire_for_processing(self, *, now: datetime) -> Job | None:
        raise NotImplementedError

    def mark_finalized(self, job: Job) -> Job:
        raise NotImplementedError

    def release_expired(self, *, now: datetime) -> Iterable[Job]:
        raise NotImplementedError

    def append_processing_logs(self, logs: Iterable[ProcessingLog]) -> None:
        raise NotImplementedError

    def list_processing_logs(self, job_id: UUID) -> list[ProcessingLog]:
        raise NotImplementedError


class _SQLiteQueueBackend(_QueueBackend):
    """SQLite implementation used in unit tests and offline environments."""

    def __init__(self, config: PostgresQueueConfig) -> None:
        self.config = config
        self._conn = self._connect(config.dsn)
        self._conn.row_factory = sqlite3.Row
        self._ensure_schema()

    # Queue operations ---------------------------------------------------

    def enqueue(self, job: Job) -> Job:
        now = job.created_at
        try:
            with self._transaction():
                self._enforce_backpressure(now)
                self._conn.execute(
                    """
                    INSERT INTO jobs (
                        id,
                        slot_id,
                        status,
                        is_finalized,
                        failure_reason,
                        expires_at,
                        created_at,
                        updated_at,
                        finalized_at,
                        payload_path,
                        provider_job_reference,
                        result_file_path,
                        result_inline_base64,
                        result_mime_type,
                        result_size_bytes,
                        result_checksum,
                        result_expires_at
                    ) VALUES (
                        :id,
                        :slot_id,
                        :status,
                        :is_finalized,
                        :failure_reason,
                        :expires_at,
                        :created_at,
                        :updated_at,
                        :finalized_at,
                        :payload_path,
                        :provider_job_reference,
                        :result_file_path,
                        :result_inline_base64,
                        :result_mime_type,
                        :result_size_bytes,
                        :result_checksum,
                        :result_expires_at
                    )
                    """,
                    self._serialize_job(job),
                )
        except sqlite3.DatabaseError as exc:  # pragma: no cover - defensive
            raise QueueUnavailableError("failed to enqueue job") from exc
        return job

    def acquire_for_processing(self, *, now: datetime) -> Job | None:
        try:
            with self._transaction():
                row = self._conn.execute(
                    """
                    SELECT *
                    FROM jobs
                    WHERE status = :pending
                      AND is_finalized = 0
                      AND expires_at >= :now
                    ORDER BY created_at
                    LIMIT 1
                    """,
                    {
                        "pending": JobStatus.PENDING.value,
                        "now": self._serialize_datetime(now),
                    },
                ).fetchone()
                if row is None:
                    return None
                self._conn.execute(
                    """
                    UPDATE jobs
                    SET status = :processing,
                        updated_at = :updated
                    WHERE id = :id
                    """,
                    {
                        "processing": JobStatus.PROCESSING.value,
                        "updated": self._serialize_datetime(now),
                        "id": row["id"],
                    },
                )
                return self._get_job(UUID(row["id"]))
        except sqlite3.DatabaseError as exc:  # pragma: no cover - defensive
            raise QueueUnavailableError("failed to acquire job") from exc

    def mark_finalized(self, job: Job) -> Job:
        try:
            with self._transaction():
                self._conn.execute(
                    """
                    UPDATE jobs
                    SET status = :status,
                        is_finalized = :is_finalized,
                        failure_reason = :failure_reason,
                        updated_at = :updated_at,
                        finalized_at = :finalized_at,
                        provider_job_reference = :provider_job_reference,
                        result_file_path = :result_file_path,
                        result_inline_base64 = :result_inline_base64,
                        result_mime_type = :result_mime_type,
                        result_size_bytes = :result_size_bytes,
                        result_checksum = :result_checksum,
                        result_expires_at = :result_expires_at
                    WHERE id = :id
                    """,
                    self._serialize_job(job),
                )
                return self._get_job(job.id)
        except sqlite3.DatabaseError as exc:  # pragma: no cover - defensive
            raise QueueUnavailableError("failed to finalize job") from exc

    def release_expired(self, *, now: datetime) -> Iterable[Job]:
        try:
            with self._transaction():
                rows = self._conn.execute(
                    """
                    SELECT id
                    FROM jobs
                    WHERE is_finalized = 0
                      AND expires_at < :now
                    """,
                    {"now": self._serialize_datetime(now)},
                ).fetchall()
                jobs: list[Job] = []
                for row in rows:
                    job_id = UUID(row["id"])
                    self._conn.execute(
                        """
                        UPDATE jobs
                        SET is_finalized = 1,
                            status = :status,
                            failure_reason = :failure,
                            updated_at = :updated,
                            finalized_at = :updated
                        WHERE id = :id
                        """,
                        {
                            "status": JobStatus.PROCESSING.value,
                            "failure": JobFailureReason.TIMEOUT.value,
                            "updated": self._serialize_datetime(now),
                            "id": str(job_id),
                        },
                    )
                    jobs.append(self._get_job(job_id))
                return jobs
        except sqlite3.DatabaseError as exc:  # pragma: no cover - defensive
            raise QueueUnavailableError("failed to release expired jobs") from exc

    def append_processing_logs(self, logs: Iterable[ProcessingLog]) -> None:
        try:
            with self._transaction():
                for log in logs:
                    self._conn.execute(
                        """
                        INSERT INTO processing_logs (
                            id,
                            job_id,
                            slot_id,
                            status,
                            occurred_at,
                            message,
                            details,
                            provider_latency_ms
                        ) VALUES (
                            :id,
                            :job_id,
                            :slot_id,
                            :status,
                            :occurred_at,
                            :message,
                            :details,
                            :provider_latency_ms
                        )
                        """,
                        self._serialize_log(log),
                    )
        except sqlite3.DatabaseError as exc:  # pragma: no cover - defensive
            raise QueueUnavailableError("failed to append processing logs") from exc

    def list_processing_logs(self, job_id: UUID) -> list[ProcessingLog]:
        cursor = self._conn.execute(
            """
            SELECT *
            FROM processing_logs
            WHERE job_id = :job_id
            ORDER BY occurred_at
            """,
            {"job_id": str(job_id)},
        )
        rows = cursor.fetchall()
        return [self._deserialize_log(row) for row in rows]

    # Internal utilities -------------------------------------------------

    def _connect(self, dsn: str) -> sqlite3.Connection:
        if dsn.startswith("sqlite://"):
            path = dsn.replace("sqlite://", "", 1)
        else:
            path = dsn
        return sqlite3.connect(path, detect_types=sqlite3.PARSE_DECLTYPES, check_same_thread=False)

    @contextmanager
    def _transaction(self) -> Iterator[sqlite3.Connection]:
        cursor = self._conn.cursor()
        cursor.execute("BEGIN")
        try:
            yield self._conn
        except Exception:
            self._conn.rollback()
            raise
        else:
            self._conn.commit()
        finally:
            cursor.close()

    def _ensure_schema(self) -> None:
        with self._transaction():
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    slot_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_finalized INTEGER NOT NULL DEFAULT 0,
                    failure_reason TEXT,
                    expires_at TEXT NOT NULL,
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL,
                    finalized_at TEXT,
                    payload_path TEXT,
                    provider_job_reference TEXT,
                    result_file_path TEXT,
                    result_inline_base64 TEXT,
                    result_mime_type TEXT,
                    result_size_bytes INTEGER,
                    result_checksum TEXT,
                    result_expires_at TEXT
                )
                """,
            )
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_logs (
                    id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    slot_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    occurred_at TEXT NOT NULL,
                    message TEXT,
                    details TEXT,
                    provider_latency_ms INTEGER
                )
                """,
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_pending
                    ON jobs(status, is_finalized, expires_at)
                """,
            )
            self._conn.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_processing_logs_job
                    ON processing_logs(job_id, occurred_at)
                """,
            )

    def _get_job(self, job_id: UUID) -> Job:
        row = self._conn.execute(
            "SELECT * FROM jobs WHERE id = :id",
            {"id": str(job_id)},
        ).fetchone()
        if row is None:  # pragma: no cover - defensive
            raise QueueUnavailableError(f"job {job_id} not found after update")
        return self._deserialize_job(row)

    def _enforce_backpressure(self, now: datetime) -> None:
        limit = self.config.max_in_flight_jobs
        if limit is None:
            return
        count = self._conn.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM jobs
            WHERE is_finalized = 0
              AND expires_at >= :now
            """,
            {"now": self._serialize_datetime(now)},
        ).fetchone()[0]
        if count >= limit:
            raise QueueBusyError("ingest queue saturated")

    @staticmethod
    def _serialize_datetime(value: datetime) -> str:
        if value.tzinfo is None:
            value = value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc).isoformat()

    def _serialize_job(self, job: Job) -> dict[str, object]:
        return {
            "id": str(job.id),
            "slot_id": job.slot_id,
            "status": job.status.value,
            "is_finalized": 1 if job.is_finalized else 0,
            "failure_reason": job.failure_reason.value if job.failure_reason else None,
            "expires_at": self._serialize_datetime(job.expires_at),
            "created_at": self._serialize_datetime(job.created_at),
            "updated_at": self._serialize_datetime(job.updated_at),
            "finalized_at": self._serialize_datetime(job.finalized_at) if job.finalized_at else None,
            "payload_path": job.payload_path,
            "provider_job_reference": job.provider_job_reference,
            "result_file_path": job.result_file_path,
            "result_inline_base64": job.result_inline_base64,
            "result_mime_type": job.result_mime_type,
            "result_size_bytes": job.result_size_bytes,
            "result_checksum": job.result_checksum,
            "result_expires_at": self._serialize_datetime(job.result_expires_at)
            if job.result_expires_at
            else None,
        }

    def _serialize_log(self, log: ProcessingLog) -> dict[str, object]:
        details = dict(log.details) if log.details is not None else None
        return {
            "id": str(log.id),
            "job_id": str(log.job_id),
            "slot_id": log.slot_id,
            "status": log.status.value,
            "occurred_at": self._serialize_datetime(log.occurred_at),
            "message": log.message,
            "details": json.dumps(details) if details is not None else None,
            "provider_latency_ms": log.provider_latency_ms,
        }

    def _deserialize_job(self, row: sqlite3.Row) -> Job:
        def _parse(value: str | None) -> datetime | None:
            return datetime.fromisoformat(value) if value is not None else None

        return Job(
            id=UUID(row["id"]),
            slot_id=row["slot_id"],
            status=JobStatus(row["status"]),
            is_finalized=bool(row["is_finalized"]),
            failure_reason=JobFailureReason(row["failure_reason"]) if row["failure_reason"] else None,
            expires_at=datetime.fromisoformat(row["expires_at"]),
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
            finalized_at=_parse(row["finalized_at"]),
            payload_path=row["payload_path"],
            provider_job_reference=row["provider_job_reference"],
            result_file_path=row["result_file_path"],
            result_inline_base64=row["result_inline_base64"],
            result_mime_type=row["result_mime_type"],
            result_size_bytes=row["result_size_bytes"],
            result_checksum=row["result_checksum"],
            result_expires_at=_parse(row["result_expires_at"]),
        )

    def _deserialize_log(self, row: sqlite3.Row) -> ProcessingLog:
        details_raw = row["details"]
        details = json.loads(details_raw) if details_raw is not None else None
        return ProcessingLog(
            id=UUID(row["id"]),
            job_id=UUID(row["job_id"]),
            slot_id=row["slot_id"],
            status=ProcessingStatus(row["status"]),
            occurred_at=datetime.fromisoformat(row["occurred_at"]),
            message=row["message"],
            details=details,
            provider_latency_ms=row["provider_latency_ms"],
        )


class _PostgresQueueBackend(_QueueBackend):
    """PostgreSQL implementation relying on psycopg for real deployments."""

    def __init__(self, config: PostgresQueueConfig) -> None:
        if psycopg is None:  # pragma: no cover - requires optional dependency
            raise QueueUnavailableError(
                "psycopg is required for PostgresJobQueue but is not installed"
            )
        self.config = config
        self._conn = psycopg.connect(config.dsn, autocommit=False)
        self._conn.row_factory = dict_row  # type: ignore[assignment]
        self._set_statement_timeout()
        self._ensure_schema()

    # Queue operations ---------------------------------------------------

    def enqueue(self, job: Job) -> Job:
        now = job.created_at
        try:
            with self._transaction() as cur:
                self._enforce_backpressure(cur, now)
                cur.execute(
                    """
                    INSERT INTO jobs (
                        id,
                        slot_id,
                        status,
                        is_finalized,
                        failure_reason,
                        expires_at,
                        created_at,
                        updated_at,
                        finalized_at,
                        payload_path,
                        provider_job_reference,
                        result_file_path,
                        result_inline_base64,
                        result_mime_type,
                        result_size_bytes,
                        result_checksum,
                        result_expires_at
                    ) VALUES (
                        %(id)s,
                        %(slot_id)s,
                        %(status)s,
                        %(is_finalized)s,
                        %(failure_reason)s,
                        %(expires_at)s,
                        %(created_at)s,
                        %(updated_at)s,
                        %(finalized_at)s,
                        %(payload_path)s,
                        %(provider_job_reference)s,
                        %(result_file_path)s,
                        %(result_inline_base64)s,
                        %(result_mime_type)s,
                        %(result_size_bytes)s,
                        %(result_checksum)s,
                        %(result_expires_at)s
                    )
                    """,
                    self._serialize_job(job),
                )
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.rollback()
            raise QueueUnavailableError("failed to enqueue job") from exc
        return job

    def acquire_for_processing(self, *, now: datetime) -> Job | None:
        try:
            with self._transaction() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = %(processing)s,
                        updated_at = %(updated)s
                    WHERE id = (
                        SELECT id
                        FROM jobs
                        WHERE status = %(pending)s
                          AND is_finalized = FALSE
                          AND expires_at >= %(now)s
                        ORDER BY created_at
                        FOR UPDATE SKIP LOCKED
                        LIMIT 1
                    )
                    RETURNING *
                    """,
                    {
                        "processing": JobStatus.PROCESSING.value,
                        "updated": now,
                        "pending": JobStatus.PENDING.value,
                        "now": now,
                    },
                )
                row = cur.fetchone()
                if row is None:
                    return None
                return self._deserialize_job(row)
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.rollback()
            raise QueueUnavailableError("failed to acquire job") from exc

    def mark_finalized(self, job: Job) -> Job:
        try:
            with self._transaction() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET status = %(status)s,
                        is_finalized = %(is_finalized)s,
                        failure_reason = %(failure_reason)s,
                        updated_at = %(updated_at)s,
                        finalized_at = %(finalized_at)s,
                        provider_job_reference = %(provider_job_reference)s,
                        result_file_path = %(result_file_path)s,
                        result_inline_base64 = %(result_inline_base64)s,
                        result_mime_type = %(result_mime_type)s,
                        result_size_bytes = %(result_size_bytes)s,
                        result_checksum = %(result_checksum)s,
                        result_expires_at = %(result_expires_at)s
                    WHERE id = %(id)s
                    RETURNING *
                    """,
                    self._serialize_job(job),
                )
                row = cur.fetchone()
                if row is None:  # pragma: no cover - defensive
                    raise QueueUnavailableError(f"job {job.id} missing during finalization")
                return self._deserialize_job(row)
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.rollback()
            raise QueueUnavailableError("failed to finalize job") from exc

    def release_expired(self, *, now: datetime) -> Iterable[Job]:
        try:
            with self._transaction() as cur:
                cur.execute(
                    """
                    UPDATE jobs
                    SET is_finalized = TRUE,
                        status = %(status)s,
                        failure_reason = %(failure)s,
                        updated_at = %(updated)s,
                        finalized_at = %(updated)s
                    WHERE is_finalized = FALSE
                      AND expires_at < %(now)s
                    RETURNING *
                    """,
                    {
                        "status": JobStatus.PROCESSING.value,
                        "failure": JobFailureReason.TIMEOUT.value,
                        "updated": now,
                        "now": now,
                    },
                )
                rows = cur.fetchall() or []
                return [self._deserialize_job(row) for row in rows]
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.rollback()
            raise QueueUnavailableError("failed to release expired jobs") from exc

    def append_processing_logs(self, logs: Iterable[ProcessingLog]) -> None:
        entries = [self._serialize_log(log) for log in logs]
        if not entries:
            return
        try:
            with self._transaction() as cur:
                cur.executemany(
                    """
                    INSERT INTO processing_logs (
                        id,
                        job_id,
                        slot_id,
                        status,
                        occurred_at,
                        message,
                        details,
                        provider_latency_ms
                    ) VALUES (
                        %(id)s,
                        %(job_id)s,
                        %(slot_id)s,
                        %(status)s,
                        %(occurred_at)s,
                        %(message)s,
                        %(details)s,
                        %(provider_latency_ms)s
                    )
                    """,
                    entries,
                )
        except Exception as exc:  # pragma: no cover - defensive
            self._conn.rollback()
            raise QueueUnavailableError("failed to append processing logs") from exc

    def list_processing_logs(self, job_id: UUID) -> list[ProcessingLog]:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                SELECT *
                FROM processing_logs
                WHERE job_id = %(job_id)s
                ORDER BY occurred_at
                """,
                {"job_id": job_id},
            )
            rows = cur.fetchall() or []
        return [self._deserialize_log(row) for row in rows]

    # Internal utilities -------------------------------------------------

    @contextmanager
    def _transaction(self):
        with self._conn.cursor() as cur:
            try:
                yield cur
            except Exception:
                self._conn.rollback()
                raise
            else:
                self._conn.commit()

    def _set_statement_timeout(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                "SET statement_timeout = %(timeout)s",
                {"timeout": f"{self.config.statement_timeout_ms}ms"},
            )

    def _ensure_schema(self) -> None:
        with self._conn.cursor() as cur:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS jobs (
                    id UUID PRIMARY KEY,
                    slot_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    is_finalized BOOLEAN NOT NULL DEFAULT FALSE,
                    failure_reason TEXT,
                    expires_at TIMESTAMPTZ NOT NULL,
                    created_at TIMESTAMPTZ NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL,
                    finalized_at TIMESTAMPTZ,
                    payload_path TEXT,
                    provider_job_reference TEXT,
                    result_file_path TEXT,
                    result_inline_base64 TEXT,
                    result_mime_type TEXT,
                    result_size_bytes BIGINT,
                    result_checksum TEXT,
                    result_expires_at TIMESTAMPTZ
                )
                """
            )
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS processing_logs (
                    id UUID PRIMARY KEY,
                    job_id UUID NOT NULL REFERENCES jobs(id) ON DELETE CASCADE,
                    slot_id TEXT NOT NULL,
                    status TEXT NOT NULL,
                    occurred_at TIMESTAMPTZ NOT NULL,
                    message TEXT,
                    details JSONB,
                    provider_latency_ms INTEGER
                )
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_jobs_pending
                    ON jobs(status, is_finalized, expires_at)
                """
            )
            cur.execute(
                """
                CREATE INDEX IF NOT EXISTS idx_processing_logs_job
                    ON processing_logs(job_id, occurred_at)
                """
            )
        self._conn.commit()

    def _enforce_backpressure(self, cur, now: datetime) -> None:
        limit = self.config.max_in_flight_jobs
        if limit is None:
            return
        cur.execute(
            """
            SELECT COUNT(*) AS cnt
            FROM jobs
            WHERE is_finalized = FALSE
              AND expires_at >= %(now)s
            """,
            {"now": now},
        )
        row = cur.fetchone()
        count = 0 if row is None else row["cnt"]
        if count >= limit:
            raise QueueBusyError("ingest queue saturated")

    @staticmethod
    def _serialize_datetime(value: datetime) -> datetime:
        if value.tzinfo is None:
            return value.replace(tzinfo=timezone.utc)
        return value.astimezone(timezone.utc)

    def _serialize_job(self, job: Job) -> dict[str, object]:
        return {
            "id": job.id,
            "slot_id": job.slot_id,
            "status": job.status.value,
            "is_finalized": job.is_finalized,
            "failure_reason": job.failure_reason.value if job.failure_reason else None,
            "expires_at": self._serialize_datetime(job.expires_at),
            "created_at": self._serialize_datetime(job.created_at),
            "updated_at": self._serialize_datetime(job.updated_at),
            "finalized_at": self._serialize_datetime(job.finalized_at)
            if job.finalized_at
            else None,
            "payload_path": job.payload_path,
            "provider_job_reference": job.provider_job_reference,
            "result_file_path": job.result_file_path,
            "result_inline_base64": job.result_inline_base64,
            "result_mime_type": job.result_mime_type,
            "result_size_bytes": job.result_size_bytes,
            "result_checksum": job.result_checksum,
            "result_expires_at": self._serialize_datetime(job.result_expires_at)
            if job.result_expires_at
            else None,
        }

    def _serialize_log(self, log: ProcessingLog) -> dict[str, object]:
        details = dict(log.details) if log.details is not None else None
        return {
            "id": log.id,
            "job_id": log.job_id,
            "slot_id": log.slot_id,
            "status": log.status.value,
            "occurred_at": self._serialize_datetime(log.occurred_at),
            "message": log.message,
            "details": details,
            "provider_latency_ms": log.provider_latency_ms,
        }

    def _deserialize_job(self, row: dict[str, object]) -> Job:
        return Job(
            id=UUID(str(row["id"])),
            slot_id=row["slot_id"],
            status=JobStatus(row["status"]),
            is_finalized=bool(row["is_finalized"]),
            failure_reason=JobFailureReason(row["failure_reason"]) if row["failure_reason"] else None,
            expires_at=row["expires_at"],
            created_at=row["created_at"],
            updated_at=row["updated_at"],
            finalized_at=row["finalized_at"],
            payload_path=row["payload_path"],
            provider_job_reference=row["provider_job_reference"],
            result_file_path=row["result_file_path"],
            result_inline_base64=row["result_inline_base64"],
            result_mime_type=row["result_mime_type"],
            result_size_bytes=row["result_size_bytes"],
            result_checksum=row["result_checksum"],
            result_expires_at=row["result_expires_at"],
        )

    def _deserialize_log(self, row: dict[str, object]) -> ProcessingLog:
        return ProcessingLog(
            id=UUID(str(row["id"])),
            job_id=UUID(str(row["job_id"])),
            slot_id=row["slot_id"],
            status=ProcessingStatus(row["status"]),
            occurred_at=row["occurred_at"],
            message=row["message"],
            details=row["details"],
            provider_latency_ms=row["provider_latency_ms"],
        )


__all__ = ["PostgresJobQueue", "PostgresQueueConfig"]

