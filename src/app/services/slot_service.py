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
        """Persist slot settings, including provider operation parameters."""

        raise NotImplementedError

    def attach_templates(
        self, slot: Slot, templates: Iterable[TemplateMedia]
    ) -> Slot:
        """Bind template media to a slot for future jobs."""

        raise NotImplementedError

    def detach_template(self, slot: Slot, template: TemplateMedia) -> Slot:
        """Remove a template binding from the slot."""

        raise NotImplementedError
