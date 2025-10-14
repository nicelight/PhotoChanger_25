"""Slot service interface."""

from __future__ import annotations

from typing import Iterable

from ..domain.models import Slot, TemplateMedia


class SlotService:
    """Operations for administering ingest slots."""

    def list_slots(self) -> list[Slot]:
        """Return all configured slots with their recent results."""

        raise NotImplementedError

    def get_slot(self, slot_id: str) -> Slot:
        """Fetch a single slot configuration by identifier."""

        raise NotImplementedError

    def update_slot(self, slot: Slot) -> Slot:
        """Persist slot settings, including ``provider_id``/``operation_id``.

        Slot contracts are defined in ``spec/contracts/schemas/Slot.json``;
        implementations should store ``settings_json`` exactly as provided so
        that worker launches remain deterministic.
        """

        raise NotImplementedError

    def attach_templates(self, slot: Slot, templates: Iterable[TemplateMedia]) -> Slot:
        """Bind template media (``setting_key`` scoped) to a slot.

        Each :class:`TemplateMedia` carries ``slot_id``/``setting_key`` metadata
        that mirrors ``TemplateMediaObject`` contracts.
        """

        raise NotImplementedError

    def detach_template(self, slot: Slot, template: TemplateMedia) -> Slot:
        """Remove a template binding from the slot."""

        raise NotImplementedError
