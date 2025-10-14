"""Repository interface for slot persistence."""

from __future__ import annotations

from typing import Iterable

from ..domain.models import Slot, TemplateMedia


class SlotRepository:
    """Data access gateway for slot entities."""

    def list_slots(self) -> list[Slot]:
        """Load all slots ordered for UI presentation."""

        raise NotImplementedError

    def get_slot(self, slot_id: str) -> Slot:
        """Load a slot by identifier."""

        raise NotImplementedError

    def save_slot(self, slot: Slot) -> Slot:
        """Persist slot updates, including provider/operation identifiers.

        Stored rows must match ``spec/contracts/schemas/Slot.json`` so that the
        admin API can emit the same structure without additional mapping.
        """

        raise NotImplementedError

    def attach_templates(
        self, slot: Slot, templates: Iterable[TemplateMedia]
    ) -> Slot:
        """Persist bindings between a slot and template media keyed by ``setting_key``.

        The persistence layer is responsible for maintaining
        ``slot_template_binding`` records that reflect
        ``TemplateMedia.setting_key``/``slot_id`` pairs.
        """

        raise NotImplementedError

    def detach_template(self, slot: Slot, template: TemplateMedia) -> Slot:
        """Remove binding between a slot and template media."""

        raise NotImplementedError
