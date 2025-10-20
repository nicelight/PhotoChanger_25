"""SQLAlchemy metadata describing the PostgreSQL queue schema."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    Table,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.sql import text

metadata = MetaData()

jobs = Table(
    "jobs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column("slot_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("is_finalized", Boolean, nullable=False, server_default=text("FALSE")),
    Column("failure_reason", Text, nullable=True),
    Column("expires_at", DateTime(timezone=True), nullable=False),
    Column("created_at", DateTime(timezone=True), nullable=False),
    Column("updated_at", DateTime(timezone=True), nullable=False),
    Column("finalized_at", DateTime(timezone=True), nullable=True),
    Column("payload_path", Text, nullable=True),
    Column("provider_job_reference", Text, nullable=True),
    Column("result_file_path", Text, nullable=True),
    Column("result_inline_base64", Text, nullable=True),
    Column("result_mime_type", Text, nullable=True),
    Column("result_size_bytes", BigInteger, nullable=True),
    Column("result_checksum", Text, nullable=True),
    Column("result_expires_at", DateTime(timezone=True), nullable=True),
)

Index(
    "ix_jobs_status_finalized_expires",
    jobs.c.status,
    jobs.c.is_finalized,
    jobs.c.expires_at,
)
Index("ix_jobs_slot_created_at", jobs.c.slot_id, jobs.c.created_at)

processing_logs = Table(
    "processing_logs",
    metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    Column(
        "job_id",
        UUID(as_uuid=True),
        ForeignKey("jobs.id", ondelete="CASCADE"),
        nullable=False,
    ),
    Column("slot_id", Text, nullable=False),
    Column("status", Text, nullable=False),
    Column("occurred_at", DateTime(timezone=True), nullable=False),
    Column("message", Text, nullable=True),
    Column("details", JSONB, nullable=True),
    Column("provider_latency_ms", Integer, nullable=True),
)

Index(
    "ix_processing_logs_job_occurred",
    processing_logs.c.job_id,
    processing_logs.c.occurred_at,
)

__all__ = ["metadata", "jobs", "processing_logs"]
