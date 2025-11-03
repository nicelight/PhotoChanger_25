"""Persistence layer for media_object records."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..db.db_models import MediaObjectModel
from ..media.media_models import MediaObject


class MediaObjectRepository:
    """Store metadata about media files associated with jobs."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def register_result(
        self,
        *,
        job_id: str,
        slot_id: str,
        path: Path,
        preview_path: Path | None,
        expires_at: datetime,
    ) -> str:
        media_id = uuid.uuid4().hex
        with self._session_factory() as session:
            session.add(
                MediaObjectModel(
                    id=media_id,
                    job_id=job_id,
                    slot_id=slot_id,
                    scope="result",
                    path=str(path),
                    preview_path=str(preview_path) if preview_path else None,
                    expires_at=expires_at,
                )
            )
            session.commit()
        return media_id

    def list_expired_results(self, reference_time: datetime) -> list[MediaObject]:
        with self._session_factory() as session:
            rows = (
                session.query(MediaObjectModel)
                .filter(
                    MediaObjectModel.scope == "result",
                    MediaObjectModel.cleaned_at.is_(None),
                    MediaObjectModel.expires_at <= reference_time,
                )
                .all()
            )
            return [self._to_domain(row) for row in rows]

    def mark_cleaned(self, media_id: str, cleaned_at: datetime) -> None:
        with self._session_factory() as session:
            model = session.get(MediaObjectModel, media_id)
            if model is None:
                raise KeyError(f"Media object '{media_id}' not found")
            model.cleaned_at = cleaned_at
            session.commit()

    @staticmethod
    def _to_domain(model: MediaObjectModel) -> MediaObject:
        return MediaObject(
            id=model.id,
            job_id=model.job_id,
            slot_id=model.slot_id,
            path=Path(model.path),
            preview_path=Path(model.preview_path) if model.preview_path else None,
            expires_at=model.expires_at,
            cleaned_at=model.cleaned_at,
        )
