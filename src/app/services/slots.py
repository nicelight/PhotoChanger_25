"""Concrete slot management service built on repository interfaces."""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping, MutableMapping, Sequence
from uuid import UUID

from ..domain.models import Slot, TemplateMedia
from ..repositories.interfaces import SlotRepository, TemplateMediaRepository
from ..schemas import (
    Pagination,
    SlotDTO,
    SlotPayload,
    SlotSearchQuery,
    SlotTemplateDTO,
    SlotTemplatePayload,
)
from .settings_service import SettingsService
from .slot_service import SlotService


class SlotValidationError(ValueError):
    """Raised when slot configuration violates validation rules."""


@dataclass(frozen=True, slots=True)
class ProviderOperation:
    """Description of a provider operation used for validation."""

    id: str
    needs: Sequence[str]


ProviderCatalog = Mapping[str, Mapping[str, ProviderOperation]]


def _load_provider_catalog(path: Path | None = None) -> ProviderCatalog:
    path = path or Path("configs/providers.json")
    if not path.exists():  # pragma: no cover - optional configuration
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    providers: dict[str, Mapping[str, ProviderOperation]] = {}
    for provider_entry in data.get("providers", []):
        provider_id = str(provider_entry.get("id"))
        operations: MutableMapping[str, ProviderOperation] = {}
        for operation in provider_entry.get("operations", []):
            operation_id = str(operation.get("id"))
            needs = tuple(str(item) for item in operation.get("needs", []))
            operations[operation_id] = ProviderOperation(id=operation_id, needs=needs)
        if provider_id:
            providers[provider_id] = dict(operations)
    return providers


@dataclass(slots=True)
class SlotManagementService(SlotService):
    """Coordinates CRUD operations for slots using repository interfaces."""

    slot_repository: SlotRepository
    template_repository: TemplateMediaRepository
    settings_service: SettingsService
    provider_catalog: ProviderCatalog | None = None
    provider_catalog_path: Path | None = None

    def __post_init__(self) -> None:
        if self.provider_catalog is None:
            self._providers = _load_provider_catalog(self.provider_catalog_path)
        else:
            self._providers = {
                provider: dict(operations)
                for provider, operations in self.provider_catalog.items()
            }

    async def list_slots(
        self, *, include_archived: bool = False
    ) -> list[Slot]:  # type: ignore[override]
        query = SlotSearchQuery(
            pagination=Pagination(page=1, per_page=0), include_archived=include_archived
        )
        page = await self.slot_repository.search(query)
        return [self._to_domain(slot, include_templates=False) for slot in page.items]

    async def get_slot(
        self, slot_id: str, *, include_templates: bool = True
    ) -> Slot:  # type: ignore[override]
        dto = await self.slot_repository.get(slot_id, with_templates=include_templates)
        return self._to_domain(dto, include_templates=include_templates)

    async def create_slot(
        self, slot: Slot, *, updated_by: str | None = None
    ) -> Slot:  # type: ignore[override]
        await self._ensure_provider_allowed(slot.provider_id)
        await self._validate_settings(
            slot_id=slot.id,
            provider_id=slot.provider_id,
            operation_id=slot.operation_id,
            settings=slot.settings_json,
        )
        payload = self._to_payload(slot, updated_by=updated_by)
        created = await self.slot_repository.create(payload)
        return self._to_domain(created, include_templates=False)

    async def update_slot(
        self,
        slot: Slot,
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:  # type: ignore[override]
        await self._ensure_provider_allowed(slot.provider_id)
        await self._validate_settings(
            slot_id=slot.id,
            provider_id=slot.provider_id,
            operation_id=slot.operation_id,
            settings=slot.settings_json,
        )
        payload = self._to_payload(slot, updated_by=updated_by)
        updated = await self.slot_repository.update(
            slot.id, payload, expected_etag=expected_etag
        )
        return self._to_domain(updated, include_templates=False)

    async def archive_slot(
        self, slot_id: str, *, expected_etag: str, updated_by: str | None = None
    ) -> Slot:  # type: ignore[override]
        _ = updated_by
        archived = await self.slot_repository.archive(slot_id, expected_etag=expected_etag)
        return self._to_domain(archived, include_templates=False)

    async def attach_templates(
        self,
        slot_id: str,
        templates: Iterable[TemplateMedia],
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:  # type: ignore[override]
        _ = updated_by
        payloads = [self._to_template_payload(template) for template in templates]
        updated = await self.slot_repository.attach_templates(
            slot_id, payloads, expected_etag=expected_etag
        )
        await self._validate_settings(
            slot_id=slot_id,
            provider_id=updated.provider_id,
            operation_id=updated.operation_id,
            settings=updated.settings_json,
        )
        return self._to_domain(updated, include_templates=True)

    async def detach_template(
        self,
        slot_id: str,
        template_id: UUID,
        *,
        expected_etag: str,
        updated_by: str | None = None,
    ) -> Slot:  # type: ignore[override]
        _ = updated_by
        updated = await self.slot_repository.detach_template(
            slot_id, template_id, expected_etag=expected_etag
        )
        await self._validate_settings(
            slot_id=slot_id,
            provider_id=updated.provider_id,
            operation_id=updated.operation_id,
            settings=updated.settings_json,
        )
        return self._to_domain(updated, include_templates=True)

    async def _ensure_provider_allowed(self, provider_id: str) -> None:
        operations = self._providers.get(provider_id)
        if operations is None:
            raise SlotValidationError(f"provider '{provider_id}' is not supported")
        settings = self.settings_service.get_settings()
        if settings.provider_keys:
            provider_status = settings.provider_keys.get(provider_id)
            if provider_status is None or not provider_status.is_configured:
                raise SlotValidationError(
                    f"provider '{provider_id}' is not configured in settings"
                )

    async def _validate_settings(
        self,
        *,
        slot_id: str,
        provider_id: str,
        operation_id: str,
        settings: Mapping[str, object],
    ) -> None:
        operations = self._providers.get(provider_id)
        if operations is None:
            raise SlotValidationError(f"provider '{provider_id}' is not supported")
        operation = operations.get(operation_id)
        if operation is None:
            raise SlotValidationError(
                f"operation '{operation_id}' is not available for provider '{provider_id}'"
            )
        missing = [key for key in operation.needs if key not in settings]
        if missing:
            raise SlotValidationError(
                f"settings_json missing required fields: {', '.join(sorted(missing))}"
            )
        template_keys = self._extract_template_keys(settings)
        if template_keys:
            templates = await self.template_repository.list_for_slot(slot_id)
            available = {template.setting_key for template in templates}
            missing_templates = sorted(template_keys - available)
            if missing_templates:
                raise SlotValidationError(
                    "settings_json references templates that are not attached: "
                    + ", ".join(missing_templates)
                )

    @staticmethod
    def _extract_template_keys(settings: Mapping[str, object]) -> set[str]:
        keys: set[str] = set()
        candidate = settings.get("template_media")
        if isinstance(candidate, Sequence) and not isinstance(candidate, (str, bytes)):
            for item in candidate:
                if isinstance(item, str):
                    keys.add(item)
                elif isinstance(item, Mapping) and "setting_key" in item:
                    keys.add(str(item["setting_key"]))
        return keys

    @staticmethod
    def _to_payload(slot: Slot, *, updated_by: str | None) -> SlotPayload:
        return SlotPayload(
            id=slot.id,
            name=slot.name,
            provider_id=slot.provider_id,
            operation_id=slot.operation_id,
            settings_json=dict(slot.settings_json),
            last_reset_at=slot.last_reset_at,
            updated_by=updated_by,
        )

    @staticmethod
    def _to_template_payload(template: TemplateMedia) -> SlotTemplatePayload:
        return SlotTemplatePayload(
            slot_id=template.slot_id,
            setting_key=template.setting_key,
            path=template.path,
            mime=template.mime,
            size_bytes=template.size_bytes,
            checksum=template.checksum,
            label=template.label,
            uploaded_by=template.uploaded_by,
            template_id=template.id,
        )

    @staticmethod
    def _to_domain(dto: SlotDTO, *, include_templates: bool) -> Slot:
        templates: list[TemplateMedia] = []
        if include_templates:
            templates = [
                TemplateMedia(
                    id=template.template_id,
                    slot_id=template.slot_id,
                    setting_key=template.setting_key,
                    path=template.path,
                    mime=template.mime,
                    size_bytes=template.size_bytes,
                    created_at=template.created_at,
                    checksum=template.checksum,
                    label=template.label,
                    uploaded_by=template.uploaded_by,
                )
                for template in getattr(dto, "templates", [])
            ]
        return Slot(
            id=dto.id,
            name=dto.name,
            provider_id=dto.provider_id,
            operation_id=dto.operation_id,
            settings_json=dict(dto.settings_json),
            last_reset_at=dto.last_reset_at,
            created_at=dto.created_at,
            updated_at=dto.updated_at,
            etag=getattr(dto, "etag", None),
            archived_at=getattr(dto, "archived_at", None),
            recent_results=[],
            templates=templates,
        )


__all__ = [
    "SlotManagementService",
    "SlotValidationError",
    "ProviderOperation",
    "ProviderCatalog",
]
