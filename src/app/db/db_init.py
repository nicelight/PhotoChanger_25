"""Database initialization helpers."""

from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy import text
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
    _migrate_slot_schema(engine)

    with session_factory() as session:
        _seed_slots(session)
        session.commit()


def _migrate_slot_schema(engine: Engine) -> None:
    """Ensure newly introduced slot columns exist (simple SQLite migration)."""
    with engine.begin() as conn:
        columns = set()
        result = conn.execute(text("PRAGMA table_info('slot')"))
        columns = {row[1] for row in result}  # pragma: no cover - depends on DB
        required_columns = {
            "display_name": "ALTER TABLE slot ADD COLUMN display_name TEXT DEFAULT ''",
            "operation": "ALTER TABLE slot ADD COLUMN operation TEXT DEFAULT 'image_edit'",
            "settings_json": "ALTER TABLE slot ADD COLUMN settings_json TEXT DEFAULT '{}'",
            "version": "ALTER TABLE slot ADD COLUMN version INTEGER DEFAULT 1",
            "updated_by": "ALTER TABLE slot ADD COLUMN updated_by TEXT",
        }
        for column, ddl in required_columns.items():
            if column not in columns:
                conn.execute(text(ddl))
        # backfill defaults for existing rows
        conn.execute(text("UPDATE slot SET display_name = id WHERE display_name IS NULL OR display_name = ''"))
        conn.execute(text("UPDATE slot SET operation = 'image_edit' WHERE operation IS NULL OR operation = ''"))
        conn.execute(text("UPDATE slot SET settings_json = '{}' WHERE settings_json IS NULL OR settings_json = ''"))
        conn.execute(text("UPDATE slot SET version = 1 WHERE version IS NULL"))


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
