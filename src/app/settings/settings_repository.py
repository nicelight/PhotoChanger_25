"""Persistence for global settings."""

from __future__ import annotations

from collections.abc import Callable
from datetime import datetime

from sqlalchemy.orm import Session

from ..db.db_models import SettingModel


class SettingsRepository:
    """Key-value wrapper backed by the settings table."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def read_all(self) -> dict[str, str]:
        with self._session_factory() as session:
            rows = session.query(SettingModel).all()
            return {row.key: row.value for row in rows}

    def upsert(self, key: str, value: str, *, updated_by: str | None = None) -> None:
        with self._session_factory() as session:
            model = session.get(SettingModel, key)
            if model is None:
                model = SettingModel(key=key)
            model.value = value
            model.updated_at = datetime.utcnow()
            model.updated_by = updated_by
            session.add(model)
            session.commit()

    def bulk_upsert(self, payload: dict[str, str], *, updated_by: str | None = None) -> None:
        with self._session_factory() as session:
            now = datetime.utcnow()
            for key, value in payload.items():
                model = session.get(SettingModel, key)
                if model is None:
                    model = SettingModel(key=key)
                model.value = value
                model.updated_at = now
                model.updated_by = updated_by
                session.add(model)
            session.commit()
