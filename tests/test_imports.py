"""Smoke-check imports for core scaffolding modules.

The test suite ensures all primary packages expose the expected symbols during
phase 2. This guards against refactors that would break wiring described in
``spec/docs/blueprints`` without providing real implementations yet.
"""

from __future__ import annotations

from importlib import import_module
from types import ModuleType

import pytest

MODULES_AND_SYMBOLS = [
    ("src.app.core.app", "create_app"),
    ("src.app.core.config", "AppConfig"),
    ("src.app.core.ui_config", "load_provider_catalog"),
    ("src.app.api", "ApiFacade"),
    ("src.app.api.client", "ApiClient"),
    ("src.app.api.routes.ingest", "ingest_slot"),
    ("src.app.api.routes.jobs", "router"),
    ("src.app.api.routes.media", "router"),
    ("src.app.api.routes.providers", "router"),
    ("src.app.api.routes.settings", "router"),
    ("src.app.api.routes.slots", "router"),
    ("src.app.api.routes.stats", "router"),
    ("src.app.api.routes.public", "router"),
    ("src.app.api.schemas", "Job"),
    ("src.app.domain", "Job"),
    ("src.app.infrastructure", "JobRepository"),
    ("src.app.infrastructure.queue.postgres", "PostgresJobQueue"),
    ("src.app.services", "ServiceRegistry"),
    ("src.app.services.job_service", "JobService"),
    ("src.app.services.slot_service", "SlotService"),
    ("src.app.services.settings_service", "SettingsService"),
    ("src.app.services.media_service", "MediaService"),
    ("src.app.services.stats_service", "StatsService"),
    ("src.app.providers", "ProviderAdapter"),
    ("src.app.providers.gemini", "GeminiProviderAdapter"),
    ("src.app.providers.turbotext", "TurbotextProviderAdapter"),
    ("src.app.ui", "UiFacade"),
    ("src.app.ui.views", "router"),
    ("src.app.workers.queue_worker", "QueueWorker"),
]


@pytest.mark.parametrize(("module_name", "symbol"), MODULES_AND_SYMBOLS)
def test_importable_symbols(module_name: str, symbol: str) -> None:
    """Import modules and verify that public symbols are exposed."""

    module: ModuleType = import_module(module_name)
    assert hasattr(module, symbol), f"{module_name} missing {symbol}"
