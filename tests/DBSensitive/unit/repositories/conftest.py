from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.db.models import Base
from src.app.utils.postgres_dsn import normalize_postgres_dsn


def _async_postgres_url(dsn: str) -> str:
    """Return a SQLAlchemy async URL using the psycopg driver."""

    url = make_url(dsn)
    driver = url.drivername
    if "+" in driver:
        base_driver = driver.split("+", 1)[0]
    else:
        base_driver = driver
    return url.set(drivername=f"{base_driver}+psycopg").render_as_string(
        hide_password=False
    )


@dataclass
class DatabaseFixture:
    sync_dsn: str

    def __post_init__(self) -> None:
        normalized = normalize_postgres_dsn(self.sync_dsn)
        self.sync_dsn = normalized.libpq
        async_dsn = _async_postgres_url(normalized.sqlalchemy)
        self.engine = create_async_engine(async_dsn, future=True)
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
def database(postgres_dsn: str) -> DatabaseFixture:
    fixture = DatabaseFixture(sync_dsn=postgres_dsn)
    asyncio.run(fixture.init_models())
    yield fixture
    asyncio.run(fixture.dispose())
