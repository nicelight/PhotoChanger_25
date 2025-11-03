"""Slot repository backed by SQLAlchemy."""

from __future__ import annotations

import json
from collections.abc import Callable
from typing import Sequence

from sqlalchemy.orm import Session

from ..db.db_models import SlotModel, SlotTemplateMediaModel
from .slots_models import Slot, SlotTemplateMedia


class SlotRepository:
    """Provide access to slot configuration stored in the database."""

    def __init__(self, session_factory: Callable[[], Session]) -> None:
        self._session_factory = session_factory

    def list_slots(self) -> Sequence[Slot]:
        with self._session_factory() as session:
            rows = session.query(SlotModel).order_by(SlotModel.id).all()
            return [self._to_domain(row) for row in rows]

    def get_slot(self, slot_id: str) -> Slot:
        with self._session_factory() as session:
            row = session.get(SlotModel, slot_id)
            if row is None:
                raise KeyError(f"Slot '{slot_id}' not found")
            return self._to_domain(row)

    def list_template_media(self, slot_id: str) -> Sequence[SlotTemplateMedia]:
        with self._session_factory() as session:
            rows = (
                session.query(SlotTemplateMediaModel)
                .filter(SlotTemplateMediaModel.slot_id == slot_id)
                .order_by(SlotTemplateMediaModel.media_kind, SlotTemplateMediaModel.id)
                .all()
            )
            return [self._to_template_domain(row) for row in rows]

    @staticmethod
    def _to_domain(model: SlotModel) -> Slot:
        settings = {}
        try:
            if model.settings_json:
                settings = json.loads(model.settings_json)
        except json.JSONDecodeError:
            settings = {}
        return Slot(
            id=model.id,
            provider=model.provider,
            operation=model.operation,
            display_name=model.display_name or model.id,
            settings=settings,
            size_limit_mb=model.size_limit_mb,
            is_active=model.is_active,
            version=model.version,
            updated_by=model.updated_by,
        )

    @staticmethod
    def _to_template_domain(model: SlotTemplateMediaModel) -> SlotTemplateMedia:
        return SlotTemplateMedia(
            id=model.id,
            slot_id=model.slot_id,
            media_kind=model.media_kind,
            media_object_id=model.media_object_id,
        )
