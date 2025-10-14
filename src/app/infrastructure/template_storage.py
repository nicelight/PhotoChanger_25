"""Abstraction for managing template media assets."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

from ..domain.models import TemplateMedia


class TemplateStorage:
    """Operations required by the admin UI to manage template media."""

    def list_templates(self) -> list[TemplateMedia]:
        """Return all stored template media entries."""

        raise NotImplementedError

    def store_template(self, template: TemplateMedia) -> TemplateMedia:
        """Persist a new template descriptor.

        Implementations must capture the physical ``path`` alongside metadata so
        that slots can reference the stored asset by ``setting_key``.
        """

        raise NotImplementedError

    def delete_template(self, template_id: UUID) -> None:
        """Remove a template and unlink associated slots."""

        raise NotImplementedError

    def bind_to_slot(
        self, *, slot_id: str, templates: Iterable[TemplateMedia]
    ) -> None:
        """Persist bindings between a slot and templates keyed by ``setting_key``.

        This mirrors the ``slot_template_binding`` relationship described in the
        SDD (``Slot N - M TemplateMedia``).
        """

        raise NotImplementedError
