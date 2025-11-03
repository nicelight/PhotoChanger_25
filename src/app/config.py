"""Application configuration builder."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Sequence

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .db.db_init import init_db


@dataclass(slots=True)
class IngestLimits:
    allowed_content_types: Sequence[str]
    slot_default_limit_mb: int
    absolute_cap_bytes: int
    chunk_size_bytes: int


@dataclass(slots=True)
class MediaPaths:
    root: Path
    results: Path
    templates: Path


@dataclass(slots=True)
class AppConfig:
    media_paths: MediaPaths
    ingest_limits: IngestLimits
    database_url: str
    engine: Engine
    session_factory: sessionmaker[Session]
    result_ttl_hours: int
    sync_response_seconds: int


def _ensure_media_paths(paths: MediaPaths) -> None:
    paths.root.mkdir(parents=True, exist_ok=True)
    paths.results.mkdir(parents=True, exist_ok=True)
    paths.templates.mkdir(parents=True, exist_ok=True)


def load_config() -> AppConfig:
    """Load configuration from environment (SQLite по умолчанию)."""
    root = Path(os.getenv("MEDIA_ROOT", "media"))
    media_paths = MediaPaths(
        root=root,
        results=root / "results",
        templates=root / "templates",
    )
    _ensure_media_paths(media_paths)

    ingest_limits = IngestLimits(
        allowed_content_types=("image/jpeg", "image/png", "image/webp"),
        slot_default_limit_mb=int(os.getenv("INGEST_SLOT_DEFAULT_LIMIT_MB", 15)),
        absolute_cap_bytes=int(os.getenv("INGEST_ABSOLUTE_CAP_BYTES", 50 * 1024 * 1024)),
        chunk_size_bytes=int(os.getenv("INGEST_CHUNK_SIZE_BYTES", 1 * 1024 * 1024)),
    )

    database_url = os.getenv("DATABASE_URL", "sqlite:///photochanger.db")
    engine = create_engine(database_url, future=True)
    session_factory: sessionmaker[Session] = sessionmaker(bind=engine, expire_on_commit=False)

    result_ttl_hours = int(os.getenv("RESULT_TTL_HOURS", 72))
    sync_response_seconds = int(os.getenv("T_SYNC_RESPONSE_SECONDS", 48))

    init_db(engine, session_factory)

    return AppConfig(
        media_paths=media_paths,
        ingest_limits=ingest_limits,
        database_url=database_url,
        engine=engine,
        session_factory=session_factory,
        result_ttl_hours=result_ttl_hours,
        sync_response_seconds=sync_response_seconds,
    )
