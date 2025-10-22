from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

try:  # pragma: no cover - optional dependency guard
    from src.app.core.app import create_app
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    if exc.name == "fastapi":
        pytest.skip("FastAPI is required for stats pipeline tests", allow_module_level=True)
    raise

try:  # pragma: no cover - optional dependency guard
    from src.app.core.config import AppConfig
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency guard
    if exc.name == "pydantic":
        pytest.skip("pydantic is required for stats pipeline tests", allow_module_level=True)
    raise

from src.app.domain.models import ProcessingStatus
from src.app.services.stats import CachedStatsService
from src.app.workers.queue_worker import QueueWorker
from tests.conftest import (
    PSYCOPG_MISSING_REASON,
    _apply_queue_migrations,
    _truncate_postgres_tables,
    psycopg,
)
from tests.mocks.providers import MockGeminiProvider, MockProviderConfig, MockProviderScenario


@pytest.mark.integration
@pytest.mark.asyncio
async def test_stats_pipeline_smoke(postgres_dsn, tmp_path):
    if psycopg is None:
        pytest.skip(PSYCOPG_MISSING_REASON)

    _apply_queue_migrations(postgres_dsn)
    _truncate_postgres_tables(postgres_dsn)

    app_config = AppConfig(
        database_url=postgres_dsn,
        stats_database_url=postgres_dsn,
        media_root=tmp_path,
        stats_slot_cache_ttl_seconds=30,
        stats_global_cache_ttl_seconds=15,
        stats_recent_results_retention_hours=1,
        stats_recent_results_limit=5,
        worker_poll_interval_ms=10,
        worker_max_poll_attempts=1,
        worker_retry_attempts=1,
        worker_retry_backoff_seconds=0.01,
        worker_request_timeout_seconds=0.2,
    )
    app = create_app(
        extra_state={
            "app_config": app_config,
            "disable_worker_pool": True,
            "disable_media_cleanup": True,
        }
    )

    try:
        registry = app.state.service_registry
        registry.register_provider_config("gemini", {"id": "gemini"})

        job_service = registry.resolve_job_service()(config=app_config)
        slot_service = registry.resolve_slot_service()(config=app_config)
        settings_service = registry.resolve_settings_service()(config=app_config)
        media_service = registry.resolve_media_service()(config=app_config)
        stats_service = registry.resolve_stats_service()(config=app_config)
        assert isinstance(stats_service, CachedStatsService)

        slot = await slot_service.get_slot("slot-001")
        settings = settings_service.get_settings()

        def populate_cache(current_time: datetime) -> None:
            stats_service.collect_global_stats(now=current_time)
            stats_service.collect_slot_stats(slot, now=current_time)
            stats_service.recent_results(slot, now=current_time)
            assert stats_service._cache  # type: ignore[attr-defined]

        now = datetime.now(timezone.utc)
        populate_cache(now)

        success_provider = MockGeminiProvider(
            MockProviderConfig(scenario=MockProviderScenario.SUCCESS)
        )
        registry.register_provider_adapter(
            "gemini", lambda *, config=None: success_provider
        )

        created_at = now
        job = job_service.create_job(
            slot,
            payload=None,
            settings=settings,
            created_at=created_at,
        )
        assert not stats_service._cache  # type: ignore[attr-defined]
        populate_cache(created_at)

        worker = QueueWorker(
            job_service=job_service,
            slot_service=slot_service,
            media_service=media_service,
            settings_service=settings_service,
            provider_factories={"gemini": lambda *, config=None: success_provider},
            provider_configs={"gemini": registry.resolve_provider_config("gemini")},
            poll_interval=app_config.worker_poll_interval_ms / 1000.0,
            max_poll_attempts=app_config.worker_max_poll_attempts,
            retry_attempts=app_config.worker_retry_attempts,
            retry_delay_seconds=app_config.worker_retry_backoff_seconds,
            request_timeout_seconds=app_config.worker_request_timeout_seconds,
        )
        try:
            processed = await worker.run_once(now=created_at + timedelta(seconds=1))
            assert processed
        finally:
            await worker.aclose()
        assert not stats_service._cache  # type: ignore[attr-defined]

        with psycopg.connect(postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM processing_logs
                    WHERE job_id = %s
                    ORDER BY occurred_at
                    """,
                    (job.id,),
                )
                statuses = [row[0] for row in cur.fetchall()]
        assert ProcessingStatus.SUCCEEDED.value in statuses

        next_now = now + timedelta(seconds=5)
        populate_cache(next_now)
        timeout_provider = MockGeminiProvider(
            MockProviderConfig(
                scenario=MockProviderScenario.TIMEOUT, timeout_polls=1
            )
        )
        registry.register_provider_adapter(
            "gemini", lambda *, config=None: timeout_provider
        )

        job_timeout = job_service.create_job(
            slot,
            payload=None,
            settings=settings,
            created_at=next_now,
        )
        assert not stats_service._cache  # type: ignore[attr-defined]
        populate_cache(next_now)

        timeout_worker = QueueWorker(
            job_service=job_service,
            slot_service=slot_service,
            media_service=media_service,
            settings_service=settings_service,
            provider_factories={"gemini": lambda *, config=None: timeout_provider},
            provider_configs={"gemini": registry.resolve_provider_config("gemini")},
            poll_interval=app_config.worker_poll_interval_ms / 1000.0,
            max_poll_attempts=app_config.worker_max_poll_attempts,
            retry_attempts=1,
            retry_delay_seconds=0.0,
            request_timeout_seconds=app_config.worker_request_timeout_seconds,
        )
        try:
            processed_timeout = await timeout_worker.run_once(
                now=next_now + timedelta(seconds=1)
            )
            assert processed_timeout
        finally:
            await timeout_worker.aclose()
        assert not stats_service._cache  # type: ignore[attr-defined]

        with psycopg.connect(postgres_dsn) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    SELECT status
                    FROM processing_logs
                    WHERE job_id = %s
                    ORDER BY occurred_at
                    """,
                    (job_timeout.id,),
                )
                timeout_statuses = [row[0] for row in cur.fetchall()]
        assert ProcessingStatus.TIMEOUT.value in timeout_statuses

    finally:
        queue = getattr(app.state, "job_queue", None)
        backend = getattr(queue, "_backend", None)
        connection = getattr(backend, "_conn", None)
        if connection is not None:
            connection.close()
        _truncate_postgres_tables(postgres_dsn)
