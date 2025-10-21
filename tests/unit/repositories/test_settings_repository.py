from __future__ import annotations

import asyncio

import pytest

from src.app.exceptions import ArchivedEntityError, ETagMismatchError
from src.app.repositories.sqlalchemy import SQLAlchemySettingsRepository
from src.app.schemas import AdminSettingPayload, Pagination, SettingsSearchQuery


@pytest.mark.unit
def test_settings_crud_and_pagination(database) -> None:
    async def scenario() -> None:
        await database.reset()
        async with database.session() as session:
            repo = SQLAlchemySettingsRepository(session)

            payload = AdminSettingPayload(
                key="settings.ingest",
                value={"ttl": 60},
                value_type="config",
                is_secret=False,
                updated_by="alice",
            )

            created = await repo.upsert(payload)
            assert created.key == payload.key
            assert created.etag

            update_payload = AdminSettingPayload(
                key="settings.ingest",
                value={"ttl": 120},
                value_type="config",
                is_secret=False,
                updated_by="bob",
            )

            updated = await repo.upsert(update_payload, expected_etag=created.etag)
            assert updated.value == {"ttl": 120}
            assert updated.updated_by == "bob"
            assert updated.etag != created.etag

            with pytest.raises(ETagMismatchError):
                await repo.upsert(update_payload, expected_etag="mismatch")

            page = await repo.list(
                SettingsSearchQuery(pagination=Pagination(page=1, per_page=1))
            )
            assert page.pagination.total == 1
            assert page.items[0].value == {"ttl": 120}

            archived = await repo.archive(update_payload.key, expected_etag=updated.etag)
            assert archived.value_type == "archived"

            with pytest.raises(ArchivedEntityError):
                await repo.archive(update_payload.key, expected_etag=archived.etag)

            secrets_payload = AdminSettingPayload(
                key="credentials.dummy",
                value="secret",
                value_type="credential",
                is_secret=True,
            )
            await repo.upsert(secrets_payload)

            public_page = await repo.list(
                SettingsSearchQuery(pagination=Pagination(page=1, per_page=10))
            )
            assert all(not item.is_secret for item in public_page.items)

            secrets_page = await repo.list(
                SettingsSearchQuery(
                    pagination=Pagination(page=1, per_page=10), include_secrets=True
                )
            )
            assert any(item.is_secret for item in secrets_page.items)

    asyncio.run(scenario())

