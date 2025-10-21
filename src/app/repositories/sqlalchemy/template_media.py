"""SQLAlchemy implementation of :class:`TemplateMediaRepository`."""

from __future__ import annotations

from typing import Iterable
from uuid import UUID

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import SlotTemplate
from ...schemas import SlotTemplateDTO


class SQLAlchemyTemplateMediaRepository:
    """Provide read access to ``slot_templates`` records."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_slot(self, slot_id: str) -> list[SlotTemplateDTO]:
        stmt = (
            sa.select(SlotTemplate)
            .where(SlotTemplate.slot_id == slot_id)
            .order_by(SlotTemplate.setting_key.asc())
        )
        result = await self._session.execute(stmt)
        return [self._to_dto(row) for row in result.scalars().all()]

    async def list_by_ids(self, template_ids: Iterable[UUID]) -> list[SlotTemplateDTO]:
        ids = list(template_ids)
        if not ids:
            return []

        stmt = sa.select(SlotTemplate).where(SlotTemplate.id.in_(ids))
        result = await self._session.execute(stmt)
        templates = result.scalars().all()

        template_map = {template.id: self._to_dto(template) for template in templates}
        return [template_map[template_id] for template_id in ids if template_id in template_map]

    @staticmethod
    def _to_dto(template: SlotTemplate) -> SlotTemplateDTO:
        return SlotTemplateDTO(
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

