from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest

pytest.importorskip(
    "aiosqlite", reason="aiosqlite is required for async SQLAlchemy tests"
)

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.db.models import Base


@dataclass
class DatabaseFixture:
    engine_url: str = "sqlite+aiosqlite:///:memory:"

    def __post_init__(self) -> None:
        self.engine = create_async_engine(self.engine_url, future=True)
        self._sessionmaker = async_sessionmaker(
            self.engine, class_=AsyncSession, expire_on_commit=False
        )

    async def init_models(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

    async def reset(self) -> None:
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
            await conn.run_sync(Base.metadata.create_all)

    async def dispose(self) -> None:
        await self.engine.dispose()

    def session(self) -> AsyncSession:
        return self._sessionmaker()


@pytest.fixture(scope="module")
def database() -> DatabaseFixture:
    fixture = DatabaseFixture()
    asyncio.run(fixture.init_models())
    yield fixture
    asyncio.run(fixture.dispose())

