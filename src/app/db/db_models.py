"""SQLAlchemy ORM models."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base declarative class."""


class SlotModel(Base):
    __tablename__ = "slot"

    id: Mapped[str] = mapped_column(String(32), primary_key=True)
    provider: Mapped[str] = mapped_column(String(64), nullable=False)
    size_limit_mb: Mapped[int] = mapped_column(Integer, nullable=False, default=15)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    jobs: Mapped[list["JobHistoryModel"]] = relationship(
        back_populates="slot",
        cascade="all, delete-orphan",
    )


class JobHistoryModel(Base):
    __tablename__ = "job_history"

    job_id: Mapped[str] = mapped_column(String(64), primary_key=True)
    slot_id: Mapped[str] = mapped_column(String(32), ForeignKey("slot.id"), nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    failure_reason: Mapped[str | None] = mapped_column(String(64))
    started_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    sync_deadline: Mapped[datetime | None] = mapped_column(DateTime)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime)
    result_path: Mapped[str | None] = mapped_column(String(512))
    result_expires_at: Mapped[datetime | None] = mapped_column(DateTime)

    slot: Mapped[SlotModel] = relationship(back_populates="jobs")
    media_objects: Mapped[list["MediaObjectModel"]] = relationship(
        back_populates="job",
        cascade="all, delete-orphan",
    )


class MediaObjectModel(Base):
    __tablename__ = "media_object"

    id: Mapped[str] = mapped_column(String(64), primary_key=True)
    job_id: Mapped[str] = mapped_column(String(64), ForeignKey("job_history.job_id"), nullable=False, index=True)
    slot_id: Mapped[str] = mapped_column(String(32), ForeignKey("slot.id"), nullable=False)
    scope: Mapped[str] = mapped_column(String(16), nullable=False)  # provider|result
    path: Mapped[str] = mapped_column(String(512), nullable=False)
    preview_path: Mapped[str | None] = mapped_column(String(512))
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    cleaned_at: Mapped[datetime | None] = mapped_column(DateTime)

    job: Mapped[JobHistoryModel] = relationship(back_populates="media_objects")


class SettingModel(Base):
    __tablename__ = "settings"

    key: Mapped[str] = mapped_column(String(64), primary_key=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)
    updated_by: Mapped[str | None] = mapped_column(String(64))
