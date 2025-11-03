"""Slot repository backed by SQLAlchemy."""

from __future__ import annotations

from collections.abc import Callable
from typing import Sequence

from sqlalchemy.orm import Session

from ..db.db_models import SlotModel
from .slots_models import Slot


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

    @staticmethod
    def _to_domain(model: SlotModel) -> Slot:
        return Slot(
            id=model.id,
            provider=model.provider,
            size_limit_mb=model.size_limit_mb,
            is_active=model.is_active,
        )
