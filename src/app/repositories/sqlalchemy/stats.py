"""SQLAlchemy implementation of :class:`StatsRepository`."""

from __future__ import annotations

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from ...db.models import ProcessingLogAggregate
from ...schemas import Page, Pagination, ProcessingAggregateDTO, StatsQuery


class SQLAlchemyStatsRepository:
    """Load aggregated processing statistics using SQLAlchemy."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def search(self, query: StatsQuery) -> Page[ProcessingAggregateDTO]:
        conditions: list[sa.ColumnElement[bool]] = []
        if query.slot_id is not None:
            conditions.append(ProcessingLogAggregate.slot_id == query.slot_id)
        if query.granularity is not None:
            conditions.append(ProcessingLogAggregate.granularity == query.granularity)
        if query.period_start is not None:
            conditions.append(ProcessingLogAggregate.period_start >= query.period_start)
        if query.period_end is not None:
            conditions.append(ProcessingLogAggregate.period_end <= query.period_end)

        stmt = (
            sa.select(ProcessingLogAggregate)
            .where(*conditions)
            .order_by(ProcessingLogAggregate.period_start.desc())
        )

        count_stmt = sa.select(sa.func.count()).select_from(
            sa.select(ProcessingLogAggregate.id).where(*conditions).subquery()
        )

        total = (await self._session.execute(count_stmt)).scalar_one()

        pagination = query.pagination
        if pagination.per_page:
            offset = (pagination.page - 1) * pagination.per_page
            stmt = stmt.limit(pagination.per_page).offset(offset)

        result = await self._session.execute(stmt)
        aggregates = [self._to_dto(row) for row in result.scalars().all()]
        return Page(
            items=aggregates,
            pagination=Pagination(
                page=pagination.page, per_page=pagination.per_page, total=total
            ),
        )

    @staticmethod
    def _to_dto(aggregate: ProcessingLogAggregate) -> ProcessingAggregateDTO:
        return ProcessingAggregateDTO(
            id=aggregate.id,
            slot_id=aggregate.slot_id,
            granularity=aggregate.granularity,
            period_start=aggregate.period_start,
            period_end=aggregate.period_end,
            counters={
                "success": aggregate.success,
                "timeouts": aggregate.timeouts,
                "provider_errors": aggregate.provider_errors,
                "cancelled": aggregate.cancelled,
                "errors": aggregate.errors,
                "ingest_count": aggregate.ingest_count,
            },
            created_at=aggregate.created_at,
            updated_at=aggregate.updated_at,
        )

