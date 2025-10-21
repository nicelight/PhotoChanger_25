from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest

try:  # pragma: no cover - optional dependency guard
    from src.app.core.app import create_app
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    if exc.name == "fastapi":
        pytest.skip("FastAPI is required for default pipeline tests", allow_module_level=True)
    raise

try:  # pragma: no cover - optional dependency guard
    from src.app.core.config import AppConfig
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    if exc.name == "pydantic":
        pytest.skip("pydantic is required for default pipeline tests", allow_module_level=True)
    raise

from src.app.domain.models import ProcessingStatus
from src.app.services.stats import CachedStatsService

from tests.conftest import (
    PSYCOPG_MISSING_REASON,
    _apply_queue_migrations,
    _truncate_postgres_tables,
    psycopg,
)


@pytest.mark.integration
def test_default_pipeline_records_logs_and_invalidates_cache(postgres_dsn):
    if psycopg is None:
        pytest.skip(PSYCOPG_MISSING_REASON)

    _apply_queue_migrations(postgres_dsn)
    _truncate_postgres_tables(postgres_dsn)

    app_config = AppConfig(database_url=postgres_dsn)
    app = create_app(
        extra_state={
            "app_config": app_config,
            "disable_worker_pool": True,
            "disable_media_cleanup": True,
        }
    )

    try:
        registry = app.state.service_registry
        stats_service = app.state.stats_service
        assert isinstance(stats_service, CachedStatsService)

        slot_service = registry.resolve_slot_service()(config=app_config)
        settings_service = registry.resolve_settings_service()(config=app_config)
        job_service = registry.resolve_job_service()(config=app_config)

        slot = asyncio.run(slot_service.get_slot("slot-001"))
        settings = settings_service.get_settings()

        now = datetime.now(timezone.utc)

        stats_service.collect_global_stats(now=now)
        stats_service.collect_slot_stats(slot, now=now)
        stats_service.recent_results(slot, now=now)
        assert stats_service._cache  # type: ignore[attr-defined]

        job = job_service.create_job(slot, payload=None, settings=settings)
        acquired = job_service.acquire_next_job(now=now)
        assert acquired is not None

        finalized = job_service.finalize_job(
            acquired,
            finalized_at=now + timedelta(seconds=1),
            result_media=None,
            inline_preview=None,
            result_checksum=None,
        )

        with psycopg.connect(postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM processing_logs
                    WHERE job_id = %s
                    ORDER BY occurred_at
                    """,
                    (finalized.id,),
                )
                rows = cur.fetchall()

        assert rows, "processing logs were not persisted"
        statuses = [row[0] for row in rows]
        assert ProcessingStatus.SUCCEEDED.value in statuses

        assert not stats_service._cache
    finally:
        queue = getattr(app.state, "job_queue", None)
        backend = getattr(queue, "_backend", None)
        connection = getattr(backend, "_conn", None)
        if connection is not None:
            connection.close()
        _truncate_postgres_tables(postgres_dsn)
