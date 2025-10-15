"""FastAPI application factory adhering to PhotoChanger contracts.

The app exposes routers generated from ``spec/contracts/openapi.yaml`` and
stores the :class:`~src.app.services.registry.ServiceRegistry` on the
application state for dependency resolution. Real dependency wiring is deferred
to implementation phases as described in the blueprints.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from fastapi import FastAPI

from ..api import ApiFacade
from ..core.config import AppConfig
from ..infrastructure.queue.postgres import PostgresJobQueue, PostgresQueueConfig
from ..services.default import (
    DefaultJobService,
    DefaultMediaService,
    DefaultSettingsService,
    DefaultSlotService,
    bootstrap_settings,
    bootstrap_slots,
)
from ..services.registry import ServiceRegistry


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
    registry: ServiceRegistry, *, app_config: AppConfig | None = None
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

    queue = PostgresJobQueue(config=PostgresQueueConfig(dsn=config.database_url))
    settings_service = DefaultSettingsService(
        settings=settings, password_hash=password_hash
    )
    slot_service = DefaultSlotService(slots=dict(slots))
    media_service = DefaultMediaService(media_root=media_root)
    job_service = DefaultJobService(queue=queue)

    registry.register_settings_service(lambda *, config=None: settings_service)
    registry.register_slot_service(lambda *, config=None: slot_service)
    registry.register_media_service(lambda *, config=None: media_service)
    registry.register_job_service(lambda *, config=None: job_service)
    registry.register_job_repository(lambda *, config=None: queue)

    return config


def create_app(extra_state: dict[str, Any] | None = None) -> FastAPI:
    """Initialise a FastAPI application with generated routers."""

    extra_state = dict(extra_state or {})
    config_override = extra_state.pop("app_config", None)
    registry = ServiceRegistry()
    app_config = _configure_dependencies(registry, app_config=config_override)

    job_queue_override = extra_state.get("job_queue")
    if job_queue_override is not None:
        registry.register_job_service(
            lambda *, config=None: DefaultJobService(queue=job_queue_override)
        )
        registry.register_job_repository(lambda *, config=None: job_queue_override)

    facade = ApiFacade(registry=registry)
    app = FastAPI(title="PhotoChanger API", version=_read_contract_version())
    app.state.service_registry = registry
    app.state.config = app_config
    if "job_queue" not in extra_state:
        extra_state["job_queue"] = registry.resolve_job_repository()(config=None)
    if extra_state:
        for key, value in extra_state.items():
            setattr(app.state, key, value)
    facade.mount(app)
    return app


__all__ = ["create_app"]
