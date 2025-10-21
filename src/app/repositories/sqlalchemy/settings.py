"""SQLAlchemy implementation of :class:`SettingsRepository`."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import AdminSetting
from ...exceptions import ArchivedEntityError, ETagMismatchError, ensure_etag, ensure_found
from ...schemas import (
    AdminSettingDTO,
    AdminSettingPayload,
    Page,
    Pagination,
    SettingsSearchQuery,
)


class SQLAlchemySettingsRepository:
    """Interact with ``admin_settings`` using an :class:`AsyncSession`."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list(self, query: SettingsSearchQuery) -> Page[AdminSettingDTO]:
        conditions: list[sa.ColumnElement[bool]] = []
        if not query.include_secrets:
            conditions.append(AdminSetting.is_secret.is_(False))
        if query.search:
            pattern = f"%{query.search.lower()}%"
            conditions.append(sa.func.lower(AdminSetting.key).like(pattern))

        pagination = query.pagination
        stmt = sa.select(AdminSetting).where(*conditions).order_by(AdminSetting.key)
        count_stmt = sa.select(sa.func.count()).select_from(
            sa.select(AdminSetting.key).where(*conditions).subquery()
        )

        total = (await self._session.execute(count_stmt)).scalar_one()

        if pagination.per_page:
            offset = (pagination.page - 1) * pagination.per_page
            stmt = stmt.limit(pagination.per_page).offset(offset)

        result = await self._session.execute(stmt)
        settings = [self._to_dto(row) for row in result.scalars().all()]
        return Page(items=settings, pagination=Pagination(page=pagination.page, per_page=pagination.per_page, total=total))

    async def get(self, key: str) -> AdminSettingDTO:
        setting = await self._session.get(AdminSetting, key)
        ensure_found(setting, entity="admin_setting", identifier=key)
        return self._to_dto(setting)

    async def upsert(
        self, payload: AdminSettingPayload, *, expected_etag: str | None = None
    ) -> AdminSettingDTO:
        async with self._session.begin():
            setting = await self._session.get(AdminSetting, payload.key, with_for_update=True)
            if setting is None:
                if expected_etag is not None:
                    raise ETagMismatchError(
                        f"admin_setting '{payload.key}' precondition failed: record missing"
                    )
                setting = AdminSetting(key=payload.key)
                self._session.add(setting)

            elif expected_etag is not None:
                ensure_etag(expected=expected_etag, actual=setting.etag, entity="admin_setting")

            now = datetime.now(timezone.utc)
            setting.value = payload.value
            setting.value_type = payload.value_type
            setting.is_secret = payload.is_secret
            setting.updated_by = payload.updated_by
            setting.updated_at = now
            setting.etag = uuid4().hex

            await self._session.flush()
            await self._session.refresh(setting)

        return self._to_dto(setting)

    async def archive(self, key: str, *, expected_etag: str) -> AdminSettingDTO:
        async with self._session.begin():
            setting = await self._session.get(AdminSetting, key, with_for_update=True)
            ensure_found(setting, entity="admin_setting", identifier=key)
            ensure_etag(expected=expected_etag, actual=setting.etag, entity="admin_setting")

            if setting.value_type == "archived":
                raise ArchivedEntityError(f"admin_setting '{key}' already archived")

            setting.value_type = "archived"
            setting.updated_at = datetime.now(timezone.utc)
            setting.etag = uuid4().hex

            await self._session.flush()
            await self._session.refresh(setting)

        return self._to_dto(setting)

    @staticmethod
    def _to_dto(setting: AdminSetting) -> AdminSettingDTO:
        return AdminSettingDTO(
            key=setting.key,
            value=setting.value,
            value_type=setting.value_type,
            is_secret=setting.is_secret,
            updated_by=setting.updated_by,
            etag=setting.etag,
            created_at=setting.created_at,
            updated_at=setting.updated_at,
        )

