"""Repository interfaces for persistence layer implementations."""

from __future__ import annotations

from typing import Iterable, Protocol
from uuid import UUID

from ..schemas import (
    AdminSettingDTO,
    AdminSettingPayload,
    Page,
    ProcessingAggregateDTO,
    SettingsSearchQuery,
    SlotDTO,
    SlotPayload,
    SlotSearchQuery,
    SlotTemplateDTO,
    SlotTemplatePayload,
    StatsQuery,
)


class SettingsRepository(Protocol):
    """Persistence operations for application-wide settings."""

    async def list(self, query: SettingsSearchQuery) -> Page[AdminSettingDTO]:
        """Return paginated settings filtered by ``query``."""

    async def get(self, key: str) -> AdminSettingDTO:
        """Return a single setting by its primary key."""

    async def upsert(
        self, payload: AdminSettingPayload, *, expected_etag: str | None = None
    ) -> AdminSettingDTO:
        """Create or update a setting, validating ``expected_etag`` when provided."""

    async def archive(self, key: str, *, expected_etag: str) -> AdminSettingDTO:
        """Soft-delete a setting while keeping audit metadata."""


class SlotRepository(Protocol):
    """Persistence operations for ingest slots and their templates."""

    async def search(self, query: SlotSearchQuery) -> Page[SlotDTO]:
        """Search for slots using filters defined in ``query``."""

    async def get(self, slot_id: str, *, with_templates: bool = False) -> SlotDTO:
        """Return a slot by identifier."""

    async def create(self, payload: SlotPayload) -> SlotDTO:
        """Persist a newly provisioned slot."""

    async def update(
        self, slot_id: str, payload: SlotPayload, *, expected_etag: str
    ) -> SlotDTO:
        """Update an existing slot, enforcing optimistic locking."""

    async def archive(self, slot_id: str, *, expected_etag: str) -> SlotDTO:
        """Archive a slot so it is excluded from default listings."""

    async def attach_templates(
        self,
        slot_id: str,
        templates: Iterable[SlotTemplatePayload],
        *,
        expected_etag: str,
    ) -> SlotDTO:
        """Attach or update templates for a slot."""

    async def detach_template(
        self, slot_id: str, template_id: UUID, *, expected_etag: str
    ) -> SlotDTO:
        """Detach a template ensuring ownership by ``slot_id``."""


class TemplateMediaRepository(Protocol):
    """Read operations for template media linked to slots."""

    async def list_for_slot(self, slot_id: str) -> list[SlotTemplateDTO]:
        """Return template bindings belonging to ``slot_id``."""

    async def list_by_ids(self, template_ids: Iterable[UUID]) -> list[SlotTemplateDTO]:
        """Return templates for provided identifiers."""


class StatsRepository(Protocol):
    """Persistence gateway for processing statistics."""

    async def search(self, query: StatsQuery) -> Page[ProcessingAggregateDTO]:
        """Return paginated aggregates filtered by ``query``."""

