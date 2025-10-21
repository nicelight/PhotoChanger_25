"""SQLAlchemy implementation of the :class:`SlotRepository`."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Iterable
from uuid import UUID, uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from ...db.models import Slot, SlotTemplate
from ...exceptions import (
    ArchivedEntityError,
    ensure_etag,
    ensure_found,
    handle_sqlalchemy_errors,
    verify_template_slot,
)
from ...schemas import (
    Page,
    Pagination,
    SlotDTO,
    SlotPayload,
    SlotSearchQuery,
    SlotTemplateDTO,
    SlotTemplatePayload,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class SQLAlchemySlotRepository:
    """Async repository for ``slots`` and their templates."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(self, query: SlotSearchQuery) -> Page[SlotDTO]:
        conditions: list[sa.ColumnElement[bool]] = []
        if not query.include_archived:
            conditions.append(Slot.archived_at.is_(None))
        if query.provider_id:
            conditions.append(Slot.provider_id == query.provider_id)
        if query.operation_id:
            conditions.append(Slot.operation_id == query.operation_id)
        if query.search:
            pattern = f"%{query.search.lower()}%"
            conditions.append(sa.func.lower(Slot.name).like(pattern))

        stmt = sa.select(Slot).where(*conditions).order_by(Slot.created_at.desc())
        count_stmt = sa.select(sa.func.count()).select_from(
            sa.select(Slot.id).where(*conditions).subquery()
        )

        total = (await self._session.execute(count_stmt)).scalar_one()

        pagination = query.pagination
        if pagination.per_page:
            offset = (pagination.page - 1) * pagination.per_page
            stmt = stmt.limit(pagination.per_page).offset(offset)

        result = await self._session.execute(stmt)
        slots = [self._build_dto(slot, include_templates=False) for slot in result.scalars().all()]
        return Page(
            items=slots,
            pagination=Pagination(
                page=pagination.page, per_page=pagination.per_page, total=total
            ),
        )

    async def get(self, slot_id: str, *, with_templates: bool = False) -> SlotDTO:
        options = [selectinload(Slot.templates)] if with_templates else []
        slot = await self._session.get(Slot, slot_id, options=options)
        ensure_found(slot, entity="slot", identifier=slot_id)
        return self._build_dto(slot, include_templates=with_templates)

    async def create(self, payload: SlotPayload) -> SlotDTO:
        now = _utcnow()
        slot = Slot(
            id=payload.id,
            name=payload.name,
            provider_id=payload.provider_id,
            operation_id=payload.operation_id,
            settings_json=dict(payload.settings_json),
            last_reset_at=payload.last_reset_at,
            created_at=now,
            updated_at=now,
            etag=uuid4().hex,
        )
        async with self._session.begin():
            self._session.add(slot)
            with handle_sqlalchemy_errors(entity="slot"):
                await self._session.flush()

        return self._build_dto(slot, include_templates=False)

    async def update(
        self, slot_id: str, payload: SlotPayload, *, expected_etag: str
    ) -> SlotDTO:
        async with self._session.begin():
            slot = await self._session.get(Slot, slot_id, with_for_update=True)
            ensure_found(slot, entity="slot", identifier=slot_id)
            ensure_etag(expected=expected_etag, actual=slot.etag, entity="slot")

            slot.name = payload.name
            slot.provider_id = payload.provider_id
            slot.operation_id = payload.operation_id
            slot.settings_json = dict(payload.settings_json)
            slot.last_reset_at = payload.last_reset_at
            slot.updated_at = _utcnow()
            slot.archived_at = None
            slot.etag = uuid4().hex

            with handle_sqlalchemy_errors(entity="slot"):
                await self._session.flush()
            await self._session.refresh(slot)

        return self._build_dto(slot, include_templates=False)

    async def archive(self, slot_id: str, *, expected_etag: str) -> SlotDTO:
        async with self._session.begin():
            slot = await self._session.get(Slot, slot_id, with_for_update=True)
            ensure_found(slot, entity="slot", identifier=slot_id)
            ensure_etag(expected=expected_etag, actual=slot.etag, entity="slot")

            if slot.archived_at is not None:
                raise ArchivedEntityError(f"slot '{slot_id}' already archived")

            slot.archived_at = _utcnow()
            slot.etag = uuid4().hex
            slot.updated_at = slot.archived_at

            with handle_sqlalchemy_errors(entity="slot"):
                await self._session.flush()
            await self._session.refresh(slot)

        return self._build_dto(slot, include_templates=False)

    async def attach_templates(
        self,
        slot_id: str,
        templates: Iterable[SlotTemplatePayload],
        *,
        expected_etag: str,
    ) -> SlotDTO:
        templates = list(templates)
        if not templates:
            return await self.get(slot_id, with_templates=True)

        async with self._session.begin():
            slot = await self._session.get(Slot, slot_id, with_for_update=True, options=[selectinload(Slot.templates)])
            ensure_found(slot, entity="slot", identifier=slot_id)
            ensure_etag(expected=expected_etag, actual=slot.etag, entity="slot")

            for payload in templates:
                verify_template_slot(slot_id=slot_id, template_slot_id=payload.slot_id)
                template = await self._find_template(slot_id, payload.setting_key)
                if template is None:
                    template = SlotTemplate(
                        id=payload.template_id or uuid4(),
                        slot_id=slot_id,
                        setting_key=payload.setting_key,
                        path=payload.path,
                        mime=payload.mime,
                        size_bytes=payload.size_bytes,
                        checksum=payload.checksum,
                        label=payload.label,
                        uploaded_by=payload.uploaded_by,
                        created_at=_utcnow(),
                    )
                    self._session.add(template)
                else:
                    template.path = payload.path
                    template.mime = payload.mime
                    template.size_bytes = payload.size_bytes
                    template.checksum = payload.checksum
                    template.label = payload.label
                    template.uploaded_by = payload.uploaded_by

            slot.etag = uuid4().hex
            slot.updated_at = _utcnow()

            with handle_sqlalchemy_errors(entity="slot"):
                await self._session.flush()
            await self._session.refresh(slot)

        return await self.get(slot_id, with_templates=True)

    async def detach_template(
        self, slot_id: str, template_id: UUID, *, expected_etag: str
    ) -> SlotDTO:
        async with self._session.begin():
            slot = await self._session.get(Slot, slot_id, with_for_update=True)
            ensure_found(slot, entity="slot", identifier=slot_id)
            ensure_etag(expected=expected_etag, actual=slot.etag, entity="slot")

            template = await self._session.get(SlotTemplate, template_id, with_for_update=True)
            ensure_found(template, entity="slot_template", identifier=str(template_id))
            verify_template_slot(slot_id=slot_id, template_slot_id=template.slot_id)

            await self._session.delete(template)

            slot.etag = uuid4().hex
            slot.updated_at = _utcnow()

            with handle_sqlalchemy_errors(entity="slot"):
                await self._session.flush()
            await self._session.refresh(slot)

        return await self.get(slot_id, with_templates=True)

    async def _find_template(self, slot_id: str, setting_key: str) -> SlotTemplate | None:
        stmt = sa.select(SlotTemplate).where(
            SlotTemplate.slot_id == slot_id,
            SlotTemplate.setting_key == setting_key,
        )
        result = await self._session.execute(stmt)
        return result.scalars().first()

    def _build_dto(self, slot: Slot, *, include_templates: bool) -> SlotDTO:
        templates: list[SlotTemplateDTO] = []
        if include_templates:
            templates = [
                SlotTemplateDTO(
                    slot_id=template.slot_id,
                    setting_key=template.setting_key,
                    path=template.path,
                    mime=template.mime,
                    size_bytes=template.size_bytes,
                    checksum=template.checksum,
                    label=template.label,
                    uploaded_by=template.uploaded_by,
                    template_id=template.id,
                    created_at=template.created_at,
                )
                for template in sorted(slot.templates, key=lambda t: t.setting_key)
            ]

        return SlotDTO(
            id=slot.id,
            name=slot.name,
            provider_id=slot.provider_id,
            operation_id=slot.operation_id,
            settings_json=slot.settings_json,
            last_reset_at=slot.last_reset_at,
            updated_by=None,
            created_at=slot.created_at,
            updated_at=slot.updated_at,
            etag=slot.etag,
            archived_at=slot.archived_at,
            templates=templates,
        )

