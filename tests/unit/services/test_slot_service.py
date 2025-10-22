from __future__ import annotations

from dataclasses import dataclass, field, replace
from datetime import datetime, timedelta, timezone
from typing import Iterable, Mapping
from uuid import UUID, uuid4

import pytest

from src.app.domain.models import (
    Job,
    JobStatus,
    MediaCacheSettings,
    Settings,
    SettingsDslrPasswordStatus,
    SettingsIngestConfig,
    SettingsProviderKeyStatus,
    Slot,
    TemplateMedia,
)
from src.app.exceptions import ETagMismatchError
from src.app.repositories.interfaces import SlotRepository, TemplateMediaRepository
from src.app.schemas import (
    Page,
    Pagination,
    SlotDTO,
    SlotPayload,
    SlotSearchQuery,
    SlotTemplateDTO,
    SlotTemplatePayload,
)
import src.app.services.default as default_services
from src.app.services.default import DefaultJobService
from src.app.services.settings_service import SettingsService
from src.app.services.slots import (
    ProviderOperation,
    SlotManagementService,
    SlotValidationError,
)


class InMemoryTemplateRepository(TemplateMediaRepository):
    def __init__(self) -> None:
        self.templates: dict[UUID, SlotTemplateDTO] = {}

    async def list_for_slot(self, slot_id: str) -> list[SlotTemplateDTO]:  # type: ignore[override]
        return [
            template
            for template in self.templates.values()
            if template.slot_id == slot_id
        ]

    async def list_by_ids(  # type: ignore[override]
        self, template_ids: Iterable[UUID]
    ) -> list[SlotTemplateDTO]:
        return [
            self.templates[template_id]
            for template_id in template_ids
            if template_id in self.templates
        ]


@dataclass(slots=True)
class InMemorySlotRepository(SlotRepository):
    template_repository: InMemoryTemplateRepository
    slots: dict[str, SlotDTO] = field(default_factory=dict)

    async def search(self, query: SlotSearchQuery) -> Page[SlotDTO]:  # type: ignore[override]
        items = [
            slot
            for slot in self.slots.values()
            if query.include_archived or slot.archived_at is None
        ]
        return Page(
            items=list(items),
            pagination=Pagination(
                page=query.pagination.page,
                per_page=query.pagination.per_page,
                total=len(items),
            ),
        )

    async def get(self, slot_id: str, *, with_templates: bool = False) -> SlotDTO:  # type: ignore[override]
        slot = self.slots[slot_id]
        templates: list[SlotTemplateDTO] = []
        if with_templates:
            templates = [
                replace(template)
                for template in await self.template_repository.list_for_slot(slot_id)
            ]
        return self._clone(slot, templates=templates)

    async def create(self, payload: SlotPayload) -> SlotDTO:  # type: ignore[override]
        now = datetime.now(timezone.utc)
        dto = SlotDTO(
            id=payload.id,
            name=payload.name,
            provider_id=payload.provider_id,
            operation_id=payload.operation_id,
            settings_json=dict(payload.settings_json),
            last_reset_at=payload.last_reset_at,
            updated_by=payload.updated_by,
            created_at=now,
            updated_at=now,
            etag=uuid4().hex,
            archived_at=None,
            templates=[],
        )
        self.slots[payload.id] = dto
        return self._clone(dto)

    async def update(
        self, slot_id: str, payload: SlotPayload, *, expected_etag: str
    ) -> SlotDTO:  # type: ignore[override]
        slot = self.slots[slot_id]
        if slot.etag != expected_etag:
            raise ETagMismatchError("slot etag mismatch")
        now = datetime.now(timezone.utc)
        updated = SlotDTO(
            id=slot.id,
            name=payload.name,
            provider_id=payload.provider_id,
            operation_id=payload.operation_id,
            settings_json=dict(payload.settings_json),
            last_reset_at=payload.last_reset_at,
            updated_by=payload.updated_by,
            created_at=slot.created_at,
            updated_at=now,
            etag=uuid4().hex,
            archived_at=None,
            templates=list(slot.templates),
        )
        self.slots[slot_id] = updated
        return self._clone(updated)

    async def archive(self, slot_id: str, *, expected_etag: str) -> SlotDTO:  # type: ignore[override]
        slot = self.slots[slot_id]
        if slot.etag != expected_etag:
            raise ETagMismatchError("slot etag mismatch")
        now = datetime.now(timezone.utc)
        archived = replace(slot, archived_at=now, updated_at=now, etag=uuid4().hex)
        self.slots[slot_id] = archived
        return self._clone(archived)

    async def attach_templates(
        self,
        slot_id: str,
        templates: Iterable[SlotTemplatePayload],
        *,
        expected_etag: str,
    ) -> SlotDTO:  # type: ignore[override]
        slot = self.slots[slot_id]
        if slot.etag != expected_etag:
            raise ETagMismatchError("slot etag mismatch")
        now = datetime.now(timezone.utc)
        for payload in templates:
            template_id = payload.template_id or uuid4()
            dto = SlotTemplateDTO(
                slot_id=slot_id,
                setting_key=payload.setting_key,
                path=payload.path,
                mime=payload.mime,
                size_bytes=payload.size_bytes,
                checksum=payload.checksum,
                label=payload.label,
                uploaded_by=payload.uploaded_by,
                template_id=template_id,
                created_at=now,
            )
            self.template_repository.templates[dto.template_id] = dto
        updated = replace(
            slot,
            etag=uuid4().hex,
            updated_at=now,
            templates=list(
                await self.template_repository.list_for_slot(slot_id)
            ),
        )
        self.slots[slot_id] = updated
        return self._clone(updated)

    async def detach_template(
        self, slot_id: str, template_id: UUID, *, expected_etag: str
    ) -> SlotDTO:  # type: ignore[override]
        slot = self.slots[slot_id]
        if slot.etag != expected_etag:
            raise ETagMismatchError("slot etag mismatch")
        self.template_repository.templates.pop(template_id, None)
        now = datetime.now(timezone.utc)
        updated = replace(
            slot,
            etag=uuid4().hex,
            updated_at=now,
            templates=list(
                await self.template_repository.list_for_slot(slot_id)
            ),
        )
        self.slots[slot_id] = updated
        return self._clone(updated)

    @staticmethod
    def _clone(slot: SlotDTO, *, templates: Iterable[SlotTemplateDTO] | None = None) -> SlotDTO:
        return SlotDTO(
            id=slot.id,
            name=slot.name,
            provider_id=slot.provider_id,
            operation_id=slot.operation_id,
            settings_json=dict(slot.settings_json),
            last_reset_at=slot.last_reset_at,
            updated_by=slot.updated_by,
            created_at=slot.created_at,
            updated_at=slot.updated_at,
            etag=slot.etag,
            archived_at=slot.archived_at,
            templates=list(templates or slot.templates),
        )


@dataclass(slots=True)
class StubRecentJobQueue:
    jobs_by_slot: dict[str, list[Job]] = field(default_factory=dict)

    def list_recent_results(
        self,
        slot_id: str,
        *,
        limit: int,
        since: datetime,
    ) -> list[Job]:
        jobs = [
            job
            for job in self.jobs_by_slot.get(slot_id, [])
            if job.finalized_at is not None and job.finalized_at >= since
        ]
        return list(jobs)


@dataclass(slots=True)
class StubSettingsService(SettingsService):
    settings: Settings

    def get_settings(self) -> Settings:  # type: ignore[override]
        return self.settings

    def verify_ingest_password(self, password: str) -> bool:  # type: ignore[override]
        return bool(password)


@pytest.fixture
def template_repository() -> InMemoryTemplateRepository:
    return InMemoryTemplateRepository()


@pytest.fixture
def slot_repository(template_repository: InMemoryTemplateRepository) -> InMemorySlotRepository:
    return InMemorySlotRepository(template_repository)


@pytest.fixture
def settings_service() -> StubSettingsService:
    now = datetime.now(timezone.utc)
    settings = Settings(
        dslr_password=SettingsDslrPasswordStatus(
            is_set=False, updated_at=now, updated_by=None
        ),
        ingest=SettingsIngestConfig(sync_response_timeout_sec=45, ingest_ttl_sec=45),
        media_cache=MediaCacheSettings(
            processed_media_ttl_hours=72, public_link_ttl_sec=45
        ),
        provider_keys={},
    )
    return StubSettingsService(settings=settings)


@pytest.fixture
def provider_catalog() -> Mapping[str, Mapping[str, ProviderOperation]]:
    return {
        "gemini": {
            "image_edit": ProviderOperation(id="image_edit", needs=("prompt",)),
        }
    }


@pytest.fixture
def service(
    slot_repository: InMemorySlotRepository,
    template_repository: InMemoryTemplateRepository,
    settings_service: StubSettingsService,
    provider_catalog: Mapping[str, Mapping[str, ProviderOperation]],
) -> SlotManagementService:
    return SlotManagementService(
        slot_repository=slot_repository,
        template_repository=template_repository,
        settings_service=settings_service,
        provider_catalog=provider_catalog,
    )


def _slot(settings: Mapping[str, object] | None = None) -> Slot:
    now = datetime.now(timezone.utc)
    return Slot(
        id="slot-001",
        name="Test Slot",
        provider_id="gemini",
        operation_id="image_edit",
        settings_json=settings if settings is not None else {"prompt": "Enhance"},
        created_at=now,
        updated_at=now,
    )


def _result_job(slot_id: str, *, finalized_at: datetime, size: int = 1024) -> Job:
    job_id = uuid4()
    return Job(
        id=job_id,
        slot_id=slot_id,
        status=JobStatus.PROCESSING,
        is_finalized=True,
        failure_reason=None,
        expires_at=finalized_at + timedelta(hours=1),
        created_at=finalized_at - timedelta(minutes=5),
        updated_at=finalized_at,
        finalized_at=finalized_at,
        payload_path=None,
        provider_job_reference=None,
        result_file_path=f"results/{job_id.hex}.png",
        result_inline_base64=None,
        result_mime_type="image/png",
        result_size_bytes=size,
        result_checksum="checksum",
        result_expires_at=finalized_at + timedelta(hours=72),
    )


@pytest.mark.anyio("asyncio")
async def test_create_and_get_slot(service: SlotManagementService) -> None:
    created = await service.create_slot(_slot())
    assert created.id == "slot-001"
    fetched = await service.get_slot("slot-001")
    assert fetched.id == created.id
    listed = await service.list_slots()
    assert [slot.id for slot in listed] == ["slot-001"]


@pytest.mark.anyio("asyncio")
async def test_update_slot_with_template_reference(
    service: SlotManagementService,
) -> None:
    created = await service.create_slot(_slot())
    template = TemplateMedia(
        id=uuid4(),
        slot_id=created.id,
        setting_key="background",
        path="template/background.png",
        mime="image/png",
        size_bytes=512,
        created_at=datetime.now(timezone.utc),
    )
    attached = await service.attach_templates(
        created.id,
        [template],
        expected_etag=created.etag or "",
    )
    updated_settings = {"prompt": "Update", "template_media": ["background"]}
    updated_slot = replace(attached, settings_json=updated_settings)
    persisted = await service.update_slot(
        updated_slot,
        expected_etag=attached.etag or "",
        updated_by="tester",
    )
    assert persisted.settings_json["template_media"] == ["background"]


@pytest.mark.anyio("asyncio")
async def test_update_slot_missing_template_fails(
    service: SlotManagementService,
) -> None:
    created = await service.create_slot(_slot())
    pending = replace(
        created,
        settings_json={"prompt": "Update", "template_media": ["absent"]},
    )
    with pytest.raises(SlotValidationError):
        await service.update_slot(pending, expected_etag=created.etag or "")


@pytest.mark.anyio("asyncio")
async def test_missing_required_field_raises(service: SlotManagementService) -> None:
    slot = _slot(settings={})
    with pytest.raises(SlotValidationError):
        await service.create_slot(slot)


@pytest.mark.anyio("asyncio")
async def test_unknown_provider_rejected(
    service: SlotManagementService,
) -> None:
    slot = replace(_slot(), provider_id="unknown")
    with pytest.raises(SlotValidationError):
        await service.create_slot(slot)


@pytest.mark.anyio("asyncio")
async def test_unknown_operation_rejected(
    service: SlotManagementService,
) -> None:
    slot = replace(_slot(), operation_id="unsupported")
    with pytest.raises(SlotValidationError):
        await service.create_slot(slot)


@pytest.mark.anyio("asyncio")
async def test_archive_slot_hidden_from_listing(service: SlotManagementService) -> None:
    created = await service.create_slot(_slot())
    archived = await service.archive_slot(created.id, expected_etag=created.etag or "")
    assert archived.archived_at is not None
    assert await service.list_slots() == []
    archived_items = await service.list_slots(include_archived=True)
    assert [slot.id for slot in archived_items] == [created.id]


@pytest.mark.anyio("asyncio")
async def test_etag_conflict_propagates(service: SlotManagementService) -> None:
    created = await service.create_slot(_slot())
    with pytest.raises(ETagMismatchError):
        await service.update_slot(created, expected_etag="invalid")


@pytest.mark.anyio("asyncio")
async def test_provider_requires_configuration(
    slot_repository: InMemorySlotRepository,
    template_repository: InMemoryTemplateRepository,
) -> None:
    now = datetime.now(timezone.utc)
    settings = Settings(
        dslr_password=SettingsDslrPasswordStatus(
            is_set=False, updated_at=now, updated_by=None
        ),
        ingest=SettingsIngestConfig(sync_response_timeout_sec=45, ingest_ttl_sec=45),
        media_cache=MediaCacheSettings(
            processed_media_ttl_hours=72, public_link_ttl_sec=45
        ),
        provider_keys={
            "gemini": SettingsProviderKeyStatus(
                is_configured=False, updated_at=now, updated_by=None, extra={}
            )
        },
    )
    service = SlotManagementService(
        slot_repository=slot_repository,
        template_repository=template_repository,
        settings_service=StubSettingsService(settings),
        provider_catalog={
            "gemini": {"image_edit": ProviderOperation(id="image_edit", needs=("prompt",))}
        },
    )
    with pytest.raises(SlotValidationError):
        await service.create_slot(_slot())


@pytest.mark.anyio("asyncio")
async def test_recent_results_sorted_and_limited(
    slot_repository: InMemorySlotRepository,
    template_repository: InMemoryTemplateRepository,
    settings_service: StubSettingsService,
    provider_catalog: Mapping[str, Mapping[str, ProviderOperation]],
    monkeypatch,
) -> None:
    queue = StubRecentJobQueue()
    now = datetime(2025, 1, 5, 12, 0, tzinfo=timezone.utc)
    jobs = [
        _result_job("slot-001", finalized_at=now - timedelta(hours=offset))
        for offset in range(12)
    ]
    queue.jobs_by_slot["slot-001"] = list(reversed(jobs)) + [
        _result_job("slot-001", finalized_at=now - timedelta(hours=100))
    ]
    job_service = DefaultJobService(queue=queue)  # type: ignore[arg-type]
    monkeypatch.setattr(default_services, "_utcnow", lambda: now)
    service = SlotManagementService(
        slot_repository=slot_repository,
        template_repository=template_repository,
        settings_service=settings_service,
        provider_catalog=provider_catalog,
        job_service=job_service,
    )

    created = await service.create_slot(_slot())
    assert len(created.recent_results) == 10
    completed_at = [result["completed_at"] for result in created.recent_results]
    assert completed_at == sorted(completed_at, reverse=True)
    assert all(
        timestamp >= now - timedelta(hours=72) for timestamp in completed_at
    )

    fetched = await service.get_slot("slot-001")
    assert fetched.recent_results == created.recent_results

    listed = await service.list_slots()
    assert listed[0].recent_results == created.recent_results
