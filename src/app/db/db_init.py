"""Database initialization helpers."""

from __future__ import annotations

import json
from datetime import datetime
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from .db_models import Base, SlotModel

DEFAULT_SLOTS = [
    {
        "id": f"slot-{index:03}",
        "provider": "gemini",
        "operation": "image_edit",
        "display_name": f"Slot {index:02}",
        "settings": {},
        "size_limit_mb": 15,
        "is_active": True,
    }
    for index in range(1, 16)
]


def init_db(engine: Engine, session_factory: sessionmaker[Session]) -> None:
    """Create tables and seed default slots if БД пуста."""
    Base.metadata.create_all(engine)

    with session_factory() as session:
        _seed_slots(session)
        session.commit()


def _seed_slots(session: Session) -> None:
    if session.query(SlotModel).count():
        return
    now = datetime.utcnow()
    for slot in DEFAULT_SLOTS:
        session.add(
            SlotModel(
                id=slot["id"],
                provider=slot["provider"],
                operation=slot["operation"],
                display_name=slot["display_name"],
                settings_json=json.dumps(slot["settings"]),
                size_limit_mb=slot["size_limit_mb"],
                is_active=slot["is_active"],
                created_at=now,
                updated_at=now,
            )
        )
