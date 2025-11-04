from __future__ import annotations

import json

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.app.db.db_models import Base, SlotModel, SlotTemplateMediaModel
from src.app.slots.slots_repository import SlotRepository


def setup_slot(session_factory: sessionmaker) -> None:
    with session_factory() as session:
        slot = SlotModel(
            id="slot-xyz",
            provider="gemini",
            operation="image_edit",
            display_name="Slot XYZ",
            settings_json=json.dumps({"prompt": "make it shiny"}),
            size_limit_mb=15,
            is_active=True,
        )
        session.add(slot)
        session.add(
            SlotTemplateMediaModel(
                slot_id="slot-xyz",
                media_kind="overlay",
                media_object_id="media-123",
            )
        )
        session.commit()


def test_get_slot_includes_template_media():
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    setup_slot(session_factory)

    repo = SlotRepository(session_factory)
    slot = repo.get_slot("slot-xyz")

    assert slot.settings["prompt"] == "make it shiny"
    assert slot.template_media
    assert slot.template_media[0].media_kind == "overlay"
    assert slot.template_media[0].media_object_id == "media-123"


def test_list_slots_returns_settings_and_media():
    engine = create_engine("sqlite:///:memory:", future=True)
    session_factory = sessionmaker(bind=engine, expire_on_commit=False)
    Base.metadata.create_all(engine)
    setup_slot(session_factory)

    repo = SlotRepository(session_factory)
    slots = repo.list_slots()

    assert len(slots) == 1
    slot = slots[0]
    assert slot.display_name == "Slot XYZ"
    assert slot.template_media[0].media_kind == "overlay"
