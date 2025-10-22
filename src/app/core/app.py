"""FastAPI application factory adhering to PhotoChanger contracts.

The app exposes routers generated from ``spec/contracts/openapi.yaml`` and
stores the :class:`~src.app.services.registry.ServiceRegistry` on the
application state for dependency resolution. Real dependency wiring is deferred
to implementation phases as described in the blueprints.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import UUID

from fastapi import FastAPI
from sqlalchemy import create_engine
from sqlalchemy.exc import NoSuchModuleError

from ..api import ApiFacade
from ..core.config import AppConfig
from ..domain.models import Job, ProcessingLog
from ..infrastructure.queue.postgres import PostgresJobQueue, PostgresQueueConfig
from ..infrastructure.sqlalchemy import SqlAlchemyStatsRepository
from ..lifecycle import run_periodic_media_cleanup
from ..services.default import (
    DefaultJobService,
    DefaultMediaService,
    DefaultSettingsService,
    DefaultSlotService,
    bootstrap_settings,
    bootstrap_slots,
)
from ..services.stats import CachedStatsService
from ..services.registry import ServiceRegistry
from ..services.container import load_stats_cache_settings, SqlAlchemyUnitOfWork
from ..workers import QueueWorker


logger = logging.getLogger(__name__)

def _read_contract_version() -> str:
    """Return the OpenAPI version declared in ``spec/contracts``."""

    version_file = (
        Path(__file__).resolve().parents[2] / "spec" / "contracts" / "VERSION.json"
    )
    try:
        data = json.loads(version_file.read_text(encoding="utf-8"))
    except FileNotFoundError:  # pragma: no cover - optional contract sync
        return "0.0.0"
    except json.JSONDecodeError:  # pragma: no cover - corrupted contract version
        return "0.0.0"
    return str(data.get("version", "0.0.0"))


def _configure_dependencies(
    registry: ServiceRegistry,
    *,
    app_config: AppConfig | None = None,
    job_queue_override: object | None = None,
) -> AppConfig:
    """Register infrastructure adapters and domain services."""

    config = app_config or AppConfig.build_default()
    media_root = config.media_root
    media_root.mkdir(parents=True, exist_ok=True)
    (media_root / "payloads").mkdir(parents=True, exist_ok=True)

    password_hash = (
        "pbkdf2_sha256$390000$70686f746f6368616e6765722d696e676573742d73616c74$"
        "4fb957db11f5dc3c987b7dd81e5ce44a25fd9c4601093921d9a48df767fdcb0a"
    )
    settings = bootstrap_settings(config, password_hash=password_hash)
    slots = bootstrap_slots(config)

    if job_queue_override is not None:
        queue = job_queue_override
    else:
        queue_config = PostgresQueueConfig(
            dsn=config.database_url,
            statement_timeout_ms=config.queue_statement_timeout_ms,
            max_in_flight_jobs=config.queue_max_in_flight_jobs,
        )
        try:
            queue = PostgresJobQueue(config=queue_config)
        except Exception as exc:  # pragma: no cover - depends on external Postgres
            logger.error(
                "PostgreSQL queue unavailable; application cannot start", exc_info=exc
            )
            raise
    stats_settings = load_stats_cache_settings(config)
    stats_dsn = config.stats_database_url or config.database_url
    try:
        stats_engine = create_engine(stats_dsn, future=True)
    except (ModuleNotFoundError, NoSuchModuleError) as exc:
        logger.warning(
            "Falling back to in-memory SQLite stats repository: %s", exc,
        )
        stats_engine = create_engine("sqlite:///:memory:", future=True)
    stats_repository = SqlAlchemyStatsRepository(stats_engine)
    stats_service = CachedStatsService(
        stats_repository,
        slot_ttl=stats_settings.slot_ttl,
        global_ttl=stats_settings.global_ttl,
        recent_results_retention=stats_settings.recent_results_retention,
        recent_results_limit=stats_settings.recent_results_limit,
    )
    settings_service = DefaultSettingsService(
        settings=settings, password_hash=password_hash
    )
    slot_service = DefaultSlotService(slots=dict(slots))
    media_service = DefaultMediaService(media_root=media_root)
    job_service = DefaultJobService(queue=queue, stats_service=stats_service)

    registry.register_settings_service(lambda *, config=None: settings_service)
    registry.register_slot_service(lambda *, config=None: slot_service)
    registry.register_media_service(lambda *, config=None: media_service)
    registry.register_job_service(lambda *, config=None: job_service)
    registry.register_stats_service(lambda *, config=None: stats_service)
    registry.register_job_repository(lambda *, config=None: queue)
    registry.register_stats_repository(lambda *, config=None: stats_repository)
    registry.register_unit_of_work(
        lambda *, config=None: SqlAlchemyUnitOfWork(stats_engine)
    )

    return config


def create_app(extra_state: dict[str, Any] | None = None) -> FastAPI:
    """Initialise a FastAPI application with generated routers."""

    extra_state = dict(extra_state or {})
    config_override = extra_state.pop("app_config", None)
    job_queue_override = extra_state.get("job_queue")
    registry = ServiceRegistry()
    app_config = _configure_dependencies(
        registry,
        app_config=config_override,
        job_queue_override=job_queue_override,
    )

    stats_service_instance = registry.resolve_stats_service()(config=app_config)
    stats_repository_factory = registry.resolve_stats_repository()
    stats_repository_instance = stats_repository_factory(config=app_config)
    extra_state.setdefault("stats_service", stats_service_instance)
    extra_state.setdefault("stats_repository", stats_repository_instance)
    extra_state.setdefault(
        "stats_unit_of_work_factory", registry.resolve_unit_of_work()
    )

    job_queue_override = extra_state.get("job_queue")
    if job_queue_override is not None:
        job_service_override = DefaultJobService(
            queue=job_queue_override, stats_service=stats_service_instance
        )
        registry.register_job_service(
            lambda *, config=None: job_service_override
        )
        registry.register_job_repository(lambda *, config=None: job_queue_override)
        extra_state.setdefault("job_service", job_service_override)

    facade = ApiFacade(registry=registry)
    app = FastAPI(title="PhotoChanger API", version=_read_contract_version())
    app.state.service_registry = registry
    app.state.config = app_config
    if "job_queue" not in extra_state:
        extra_state["job_queue"] = registry.resolve_job_repository()(config=None)
    if extra_state:
        for key, value in extra_state.items():
            setattr(app.state, key, value)
    app.state.worker_pool = []
    app.state.worker_tasks = []
    app.state.worker_shutdown_event = None
    app.state.media_cleanup_task = None
    app.state.media_cleanup_shutdown_event = None
    if not hasattr(app.state, "media_cleanup_interval_seconds"):
        app.state.media_cleanup_interval_seconds = 15 * 60

    async def _startup_worker_pool() -> None:
        if getattr(app.state, "disable_worker_pool", False):
            logger.info("Worker pool startup skipped: disabled via app state")
            return
        provider_factories = registry.provider_snapshot()
        if not provider_factories:
            logger.info(
                "Worker pool startup skipped: no provider adapters registered"
            )
            return
        job_service = registry.resolve_job_service()(config=app_config)
        slot_service = registry.resolve_slot_service()(config=app_config)
        settings_service = registry.resolve_settings_service()(config=app_config)
        media_service = registry.resolve_media_service()(config=app_config)
        stats_service = registry.resolve_stats_service()(config=app_config)
        provider_configs = {
            provider_id: registry.resolve_provider_config(provider_id)
            for provider_id in provider_factories
        }
        worker_count = min(4, app_config.queue_max_in_flight_jobs)
        if worker_count <= 0:
            return
        shutdown_event = asyncio.Event()
        workers: list[QueueWorker] = []
        tasks: list[asyncio.Task[None]] = []
        poll_interval = max(app_config.worker_poll_interval_ms / 1000.0, 0.001)
        retry_delay = max(float(app_config.worker_retry_backoff_seconds), 0.0)
        request_timeout = max(float(app_config.worker_request_timeout_seconds), 0.1)
        for index in range(worker_count):
            worker = QueueWorker(
                job_service=job_service,
                slot_service=slot_service,
                media_service=media_service,
                settings_service=settings_service,
                provider_factories=provider_factories,
                provider_configs=provider_configs,
                poll_interval=poll_interval,
                max_poll_attempts=app_config.worker_max_poll_attempts,
                retry_attempts=app_config.worker_retry_attempts,
                retry_delay_seconds=retry_delay,
                request_timeout_seconds=request_timeout,
            )
            task = asyncio.create_task(
                worker.run_forever(worker_id=index, shutdown_event=shutdown_event),
                name=f"photochanger-worker-{index}",
            )
            workers.append(worker)
            tasks.append(task)
        app.state.worker_pool = workers
        app.state.worker_tasks = tasks
        app.state.worker_shutdown_event = shutdown_event

    async def _shutdown_worker_pool() -> None:
        shutdown_event = getattr(app.state, "worker_shutdown_event", None)
        if shutdown_event is not None:
            shutdown_event.set()
        tasks: list[asyncio.Task[None]] = getattr(app.state, "worker_tasks", [])
        for task in tasks:
            task.cancel()
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        workers: list[QueueWorker] = getattr(app.state, "worker_pool", [])
        for worker in workers:
            await worker.aclose()
        app.state.worker_pool = []
        app.state.worker_tasks = []
        app.state.worker_shutdown_event = None

    async def _startup_media_cleanup() -> None:
        if getattr(app.state, "disable_media_cleanup", False):
            logger.info("Media cleanup startup skipped: disabled via app state")
            return
        job_service = registry.resolve_job_service()(config=app_config)
        media_service = registry.resolve_media_service()(config=app_config)
        interval = float(getattr(app.state, "media_cleanup_interval_seconds", 15 * 60))
        shutdown_event = asyncio.Event()
        task = asyncio.create_task(
            run_periodic_media_cleanup(
                media_service=media_service,
                job_service=job_service,
                shutdown_event=shutdown_event,
                interval_seconds=interval,
            ),
            name="photochanger-media-cleanup",
        )
        app.state.media_cleanup_task = task
        app.state.media_cleanup_shutdown_event = shutdown_event

    async def _shutdown_media_cleanup() -> None:
        shutdown_event = getattr(app.state, "media_cleanup_shutdown_event", None)
        if shutdown_event is not None:
            shutdown_event.set()
        task: asyncio.Task[None] | None = getattr(app.state, "media_cleanup_task", None)
        if task is not None:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
        app.state.media_cleanup_task = None
        app.state.media_cleanup_shutdown_event = None

    facade.mount(app)
    app.add_event_handler("startup", _startup_worker_pool)
    app.add_event_handler("startup", _startup_media_cleanup)
    app.add_event_handler("shutdown", _shutdown_media_cleanup)
    app.add_event_handler("shutdown", _shutdown_worker_pool)
    return app


__all__ = ["create_app"]
