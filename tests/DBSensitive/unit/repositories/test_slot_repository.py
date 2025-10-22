from __future__ import annotations

import asyncio

import pytest

from src.app.exceptions import (
    ArchivedEntityError,
    ETagMismatchError,
    IntegrityConstraintViolation,
    TemplateBindingError,
)
from src.app.repositories.sqlalchemy import SQLAlchemySlotRepository
from src.app.schemas import (
    Pagination,
    SlotPayload,
    SlotSearchQuery,
    SlotTemplatePayload,
)


def _payload(slot_id: str, *, name: str = "Test slot", provider: str = "provider-a") -> SlotPayload:
    return SlotPayload(
        id=slot_id,
        name=name,
        provider_id=provider,
        operation_id="op-1",
        settings_json={"enabled": True},
        last_reset_at=None,
    )


@pytest.mark.unit
def test_slot_crud_templates_and_pagination(database) -> None:
    async def scenario() -> None:
        await database.reset()
        async with database.session() as session:
            repo = SQLAlchemySlotRepository(session)

            created = await repo.create(_payload("slot-001"))
            assert created.id == "slot-001"

            page = await repo.search(
                SlotSearchQuery(pagination=Pagination(page=1, per_page=10))
            )
            assert page.pagination.total == 1

            fetched = await repo.get("slot-001", with_templates=True)
            assert fetched.etag == created.etag

            updated = await repo.update(
                "slot-001",
                _payload("slot-001", name="Renamed"),
                expected_etag=fetched.etag,
            )
            assert updated.name == "Renamed"

            with pytest.raises(ETagMismatchError):
                await repo.update(
                    "slot-001", _payload("slot-001"), expected_etag="bogus-etag"
                )

            template_payload = SlotTemplatePayload(
                slot_id="slot-001",
                setting_key="background",
                path="/assets/bg.png",
                mime="image/png",
                size_bytes=128,
            )
            slot_with_template = await repo.attach_templates(
                "slot-001", [template_payload], expected_etag=updated.etag
            )
            assert len(slot_with_template.templates) == 1

            template_id = slot_with_template.templates[0].template_id

            slot_after_detach = await repo.detach_template(
                "slot-001", template_id, expected_etag=slot_with_template.etag
            )
            assert not slot_after_detach.templates

            with pytest.raises(TemplateBindingError):
                await repo.attach_templates(
                    "slot-001",
                    [
                        SlotTemplatePayload(
                            slot_id="slot-999",
                            setting_key="background",
                            path="/assets/bg.png",
                            mime="image/png",
                            size_bytes=256,
                        )
                    ],
                    expected_etag=slot_after_detach.etag,
                )

            archived = await repo.archive(
                "slot-001", expected_etag=slot_after_detach.etag
            )
            assert archived.archived_at is not None

            active_page = await repo.search(
                SlotSearchQuery(pagination=Pagination(page=1, per_page=10))
            )
            assert active_page.pagination.total == 0

            archived_page = await repo.search(
                SlotSearchQuery(
                    pagination=Pagination(page=1, per_page=10), include_archived=True
                )
            )
            assert archived_page.pagination.total == 1

            with pytest.raises(ArchivedEntityError):
                await repo.archive("slot-001", expected_etag=archived.etag)

    asyncio.run(scenario())


@pytest.mark.unit
def test_slot_unique_constraint(database) -> None:
    async def scenario() -> None:
        await database.reset()
        async with database.session() as session:
            repo = SQLAlchemySlotRepository(session)

            await repo.create(_payload("slot-010"))

            with pytest.raises(IntegrityConstraintViolation):
                await repo.create(_payload("slot-010"))

    asyncio.run(scenario())

