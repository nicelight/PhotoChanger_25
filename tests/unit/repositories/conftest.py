from __future__ import annotations

import asyncio
from dataclasses import dataclass

import pytest
from sqlalchemy.engine import URL, make_url
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.app.db.models import Base


def _async_postgres_url(dsn: str) -> str:
    """Return a SQLAlchemy async URL using the psycopg driver."""

    if "://" in dsn:
        url = make_url(dsn)
        driver = url.drivername
        if "+" in driver:
            base_driver = driver.split("+", 1)[0]
        else:
            base_driver = driver
        return str(url.set(drivername=f"{base_driver}+psycopg"))

    from psycopg.conninfo import conninfo_to_dict

    info = conninfo_to_dict(dsn)
    user = info.pop("user", None)
    password = info.pop("password", None)
    host = info.pop("host", None)
    port = info.pop("port", None)
    database = info.pop("dbname", None)
    query = info or None

    return str(
        URL.create(
            drivername="postgresql+psycopg",
            username=user,
            password=password,
            host=host,
            port=int(port) if port is not None else None,
            database=database,
            query=query,
        )
    )


@dataclass
class DatabaseFixture:
    sync_dsn: str

    def __post_init__(self) -> None:
        self.engine = create_async_engine(_async_postgres_url(self.sync_dsn), future=True)
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
