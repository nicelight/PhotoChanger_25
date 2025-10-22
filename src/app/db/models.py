"""Declarative SQLAlchemy models for admin data storage."""

from __future__ import annotations

from datetime import datetime
from typing import Any, Optional
from uuid import UUID as UUIDType, uuid4

import sqlalchemy as sa
from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    MetaData,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB, UUID as PGUUID
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


NAMING_CONVENTION = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    """Base class that applies a deterministic naming convention."""

    metadata = MetaData(naming_convention=NAMING_CONVENTION)


JSONType = JSONB(astext_type=Text())
"""Canonical JSONB column type for PostgreSQL-backed tables."""


class AdminSetting(Base):
    """Key-value store for global administrative configuration."""

    __tablename__ = "admin_settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[Any | None] = mapped_column(JSONType, nullable=True)
    value_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    is_secret: Mapped[bool] = mapped_column(
        sa.Boolean(), nullable=False, default=False, server_default=sa.text("FALSE")
    )
    etag: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=lambda: uuid4().hex,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
    updated_by: Mapped[str | None] = mapped_column(String(64), nullable=True)

    __table_args__ = (
        CheckConstraint("length(key) > 0", name="ck_admin_settings_key_length"),
        Index("ix_admin_settings_updated_at", "updated_at"),
    )


class Slot(Base):
    """Static ingest slot configuration for the admin API."""

    __tablename__ = "slots"

    id: Mapped[str] = mapped_column(String(16), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    provider_id: Mapped[str] = mapped_column(String(64), nullable=False)
    operation_id: Mapped[str] = mapped_column(String(64), nullable=False)
    settings_json: Mapped[Any] = mapped_column(JSONType, nullable=False)
    last_reset_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )
    etag: Mapped[str] = mapped_column(
        String(32),
        nullable=False,
        default=lambda: uuid4().hex,
    )
    archived_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    templates: Mapped[list["SlotTemplate"]] = relationship(
        back_populates="slot", cascade="all, delete-orphan"
    )

    __table_args__ = (
        CheckConstraint("id ~ '^slot-[0-9]{3}$'", name="ck_slots_id_format"),
        Index("ix_slots_provider_operation", "provider_id", "operation_id"),
        Index("ix_slots_updated_at", "updated_at"),
    )


class SlotTemplate(Base):
    """Template asset bound to a slot configuration parameter."""

    __tablename__ = "slot_templates"

    id: Mapped[UUIDType] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slot_id: Mapped[str] = mapped_column(
        String(16), ForeignKey("slots.id", ondelete="CASCADE"), nullable=False
    )
    setting_key: Mapped[str] = mapped_column(String(128), nullable=False)
    path: Mapped[str] = mapped_column(Text, nullable=False)
    mime: Mapped[str] = mapped_column(String(128), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    checksum: Mapped[str | None] = mapped_column(String(64), nullable=True)
    label: Mapped[str | None] = mapped_column(String(128), nullable=True)
    uploaded_by: Mapped[str | None] = mapped_column(String(64), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )

    slot: Mapped["Slot"] = relationship(back_populates="templates")

    __table_args__ = (
        UniqueConstraint("slot_id", "setting_key", name="uq_slot_templates_slot_key"),
        Index("ix_slot_templates_slot_id", "slot_id"),
    )


class ProcessingLogAggregate(Base):
    """Aggregated counters derived from processing logs for analytics."""

    __tablename__ = "processing_log_aggregates"

    id: Mapped[UUIDType] = mapped_column(
        PGUUID(as_uuid=True), primary_key=True, default=uuid4
    )
    slot_id: Mapped[Optional[str]] = mapped_column(
        String(16), ForeignKey("slots.id", ondelete="CASCADE"), nullable=True
    )
    granularity: Mapped[str] = mapped_column(String(8), nullable=False)
    period_start: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    period_end: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    success: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    timeouts: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    provider_errors: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    cancelled: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    errors: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    ingest_count: Mapped[int] = mapped_column(
        Integer, nullable=False, default=0, server_default=sa.text("0")
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=sa.func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=sa.func.now(),
        onupdate=sa.func.now(),
    )

    __table_args__ = (
        UniqueConstraint(
            "slot_id", "granularity", "period_start", "period_end",
            name="uq_processing_log_aggregates_scope_period",
        ),
        Index(
            "ix_processing_log_aggregates_slot_period",
            "slot_id",
            "period_start",
        ),
        Index("ix_processing_log_aggregates_period_end", "period_end"),
        CheckConstraint("period_end >= period_start", name="ck_processing_log_aggregates_period"),
    )


__all__ = [
    "Base",
    "AdminSetting",
    "Slot",
    "SlotTemplate",
    "ProcessingLogAggregate",
]
