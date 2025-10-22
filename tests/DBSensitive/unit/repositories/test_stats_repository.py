from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from uuid import uuid4

import pytest

from src.app.db.models import ProcessingLogAggregate
from src.app.repositories.sqlalchemy import SQLAlchemyStatsRepository
from src.app.schemas import Pagination, StatsQuery


@pytest.mark.unit
def test_stats_pagination_and_filters(database) -> None:
    async def scenario() -> None:
        await database.reset()
        now = datetime.now(timezone.utc)
        rows = [
            ProcessingLogAggregate(
                id=uuid4(),
                slot_id="slot-001",
                granularity="day",
                period_start=now - timedelta(days=idx),
                period_end=now - timedelta(days=idx - 1),
                success=idx,
                timeouts=0,
                provider_errors=0,
                cancelled=0,
                errors=0,
                ingest_count=idx,
                created_at=now,
                updated_at=now,
            )
            for idx in range(1, 4)
        ]
        rows.append(
            ProcessingLogAggregate(
                id=uuid4(),
                slot_id=None,
                granularity="week",
                period_start=now - timedelta(weeks=1),
                period_end=now,
                success=10,
                timeouts=1,
                provider_errors=2,
                cancelled=0,
                errors=1,
                ingest_count=14,
                created_at=now,
                updated_at=now,
            )
        )

        async with database.session() as session:
            async with session.begin():
                session.add_all(rows)

            repo = SQLAlchemyStatsRepository(session)

            page = await repo.search(
                StatsQuery(pagination=Pagination(page=1, per_page=2))
            )
            assert page.pagination.total == 4
            assert len(page.items) == 2

            filtered = await repo.search(
                StatsQuery(
                    pagination=Pagination(page=1, per_page=10),
                    slot_id="slot-001",
                    granularity="day",
                )
            )
            assert filtered.pagination.total == 3
            assert all(item.slot_id == "slot-001" for item in filtered.items)

            ranged = await repo.search(
                StatsQuery(
                    pagination=Pagination(page=1, per_page=10),
                    period_start=now - timedelta(days=2),
                    period_end=now,
                )
            )
            assert ranged.pagination.total == 3

    asyncio.run(scenario())

