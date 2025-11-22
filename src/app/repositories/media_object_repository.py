"""Persistence layer for media_object records."""

from __future__ import annotations

import uuid
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from sqlalchemy.orm import Session

from ..db.db_models import MediaObjectModel, SlotTemplateMediaModel
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
        return self._register_media(
            scope="result",
            job_id=job_id,
            slot_id=slot_id,
            path=path,
            preview_path=preview_path,
            expires_at=expires_at,
        )

    def register_temp(
        self,
        *,
        job_id: str,
        slot_id: str,
        path: Path,
        expires_at: datetime,
    ) -> str:
        return self._register_media(
            scope="provider",
            job_id=job_id,
            slot_id=slot_id,
            path=path,
            preview_path=None,
            expires_at=expires_at,
        )

    def list_expired_results(self, reference_time: datetime) -> list[MediaObject]:
        return self.list_expired_by_scope("result", reference_time)

    def list_expired_by_scope(
        self, scope: str, reference_time: datetime
    ) -> list[MediaObject]:
        with self._session_factory() as session:
            rows = (
                session.query(MediaObjectModel)
                .filter(
                    MediaObjectModel.scope == scope,
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

    def get_media(self, media_id: str) -> MediaObject:
        """Return media object by ID, guarding against cleaned records."""
        with self._session_factory() as session:
            model = session.get(MediaObjectModel, media_id)
            if model is None:
                raise KeyError(f"Media object '{media_id}' not found")
            if model.cleaned_at is not None:
                raise KeyError(f"Media object '{media_id}' has been cleaned")
            return self._to_domain(model)

    def get_media_by_kind(self, slot_id: str, media_kind: str) -> MediaObject:
        """Resolve single media object by slot and media kind."""
        with self._session_factory() as session:
            query = (
                session.query(SlotTemplateMediaModel)
                .filter(
                    SlotTemplateMediaModel.slot_id == slot_id,
                    SlotTemplateMediaModel.media_kind == media_kind,
                )
                .order_by(SlotTemplateMediaModel.created_at.desc())
            )
            rows = query.all()
            if not rows:
                raise KeyError(
                    f"Template media kind '{media_kind}' not found for slot '{slot_id}'"
                )
            if len(rows) > 1:
                raise ValueError(
                    f"Multiple template media entries found for slot '{slot_id}' and kind '{media_kind}'"
                )
            media_id = rows[0].media_object_id
        return self.get_media(media_id)

    def _register_media(
        self,
        *,
        scope: str,
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
                    scope=scope,
                    path=str(path),
                    preview_path=str(preview_path) if preview_path else None,
                    expires_at=expires_at,
                )
            )
            session.commit()
        return media_id

    @staticmethod
    def _to_domain(model: MediaObjectModel) -> MediaObject:
        return MediaObject(
            id=model.id,
            job_id=model.job_id,
            slot_id=model.slot_id,
            path=Path(model.path),
            preview_path=Path(model.preview_path) if model.preview_path else None,
            expires_at=model.expires_at,
            scope=model.scope,
            cleaned_at=model.cleaned_at,
        )
