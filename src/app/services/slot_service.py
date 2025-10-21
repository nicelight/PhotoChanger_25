"""Slot service interface."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from ..domain.models import Slot, TemplateMedia


class SlotService:
    """Operations for administering ingest slots."""

    async def list_slots(self, *, include_archived: bool = False) -> list[Slot]:
        """Return all configured slots with their recent results."""

        raise NotImplementedError

    async def get_slot(
        self, slot_id: str, *, include_templates: bool = True
    ) -> Slot:
        """Fetch a single slot configuration by identifier."""

        raise NotImplementedError

    async def create_slot(
        self, slot: Slot, *, updated_by: str | None = None
    ) -> Slot:
        """Persist a new slot along with its settings."""

        raise NotImplementedError

    async def update_slot(
        self,
        slot: Slot,
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:
        """Persist slot settings, including ``provider_id``/``operation_id``.

        Slot contracts are defined in ``spec/contracts/schemas/Slot.json``;
        implementations should store ``settings_json`` exactly as provided so
        that worker launches remain deterministic.
        """

        raise NotImplementedError

    async def archive_slot(
        self, slot_id: str, *, expected_etag: str, updated_by: str | None = None
    ) -> Slot:
        """Archive a slot so it is hidden from default listings."""

        raise NotImplementedError

    async def attach_templates(
        self,
        slot_id: str,
        templates: Iterable[TemplateMedia],
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:
        """Bind template media (``setting_key`` scoped) to a slot.

        Each :class:`TemplateMedia` carries ``slot_id``/``setting_key`` metadata
        that mirrors ``TemplateMediaObject`` contracts.
        """

        raise NotImplementedError

    async def detach_template(
        self,
        slot_id: str,
        template_id: UUID,
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:
        """Remove a template binding from the slot."""

        raise NotImplementedError
