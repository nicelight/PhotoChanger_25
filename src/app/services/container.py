"""Service composition helpers."""

from __future__ import annotations

import json
from pathlib import Path
from dataclasses import dataclass
from datetime import timedelta
from typing import Any, Mapping

from sqlalchemy import create_engine
from sqlalchemy.engine import Engine

from ..plugins.base import PluginFactory, PluginKey
from ..core.config import AppConfig
from ..services.stats import CachedStatsService
from ..infrastructure.sqlalchemy import SqlAlchemyStatsRepository
from ..infrastructure.unit_of_work import UnitOfWork
from .registry import ServiceRegistry


@dataclass(frozen=True)
class _StatsCacheConfig:
    slot_ttl: timedelta
    global_ttl: timedelta
    recent_results_retention: timedelta
    recent_results_limit: int


class SqlAlchemyUnitOfWork(UnitOfWork):
    """Synchronous SQLAlchemy unit of work used by scaffolding layers."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._connection: Any | None = None

    def __enter__(self) -> "SqlAlchemyUnitOfWork":  # pragma: no cover - trivial
        self._connection = self._engine.begin()
        return self

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:  # pragma: no cover - trivial
        if self._connection is None:
            return
        try:
            if exc_type is not None:
                self._connection.rollback()
            else:
                self._connection.commit()
        finally:
            self._connection.close()
            self._connection = None

    def commit(self) -> None:  # pragma: no cover - trivial
        if self._connection is None:
            raise RuntimeError("unit of work is not active")
        self._connection.commit()
        self._connection = self._engine.begin()

    def rollback(self) -> None:  # pragma: no cover - trivial
        if self._connection is None:
            return
        self._connection.rollback()
        self._connection = self._engine.begin()


_ENGINE_CACHE: dict[str, Engine] = {}


def _load_provider_configs(config_path: Path) -> Mapping[str, Mapping[str, object]]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    providers = raw.get("providers", [])
    mapping: dict[str, Mapping[str, object]] = {}
    for entry in providers:
        provider_id = entry.get("id")
        if not provider_id:
            continue
        mapping[str(provider_id)] = dict(entry)
    return mapping


def _load_stats_cache_config(config_path: Path) -> _StatsCacheConfig:
    defaults = {
        "slot_ttl_seconds": 5 * 60,
        "global_ttl_seconds": 60,
        "recent_results_retention_hours": 72,
        "recent_results_limit": 10,
    }
    if config_path.exists():
        try:
            with config_path.open("r", encoding="utf-8") as handle:
                raw = json.load(handle)
        except json.JSONDecodeError:  # pragma: no cover - defensive
            raw = {}
    else:
        raw = {}
    cache_section = raw.get("cache", {})
    slot_seconds = int(cache_section.get("slot_ttl_seconds", defaults["slot_ttl_seconds"]))
    global_seconds = int(
        cache_section.get("global_ttl_seconds", defaults["global_ttl_seconds"])
    )
    slot_seconds = max(0, slot_seconds)
    global_seconds = max(0, global_seconds)
    recent_section = raw.get("recent_results", {})
    retention_hours = int(
        recent_section.get(
            "retention_hours", defaults["recent_results_retention_hours"]
        )
    )
    retention_hours = max(1, retention_hours)
    limit = int(recent_section.get("limit", defaults["recent_results_limit"]))
    limit = max(1, limit)
    return _StatsCacheConfig(
        slot_ttl=timedelta(seconds=slot_seconds),
        global_ttl=timedelta(seconds=global_seconds),
        recent_results_retention=timedelta(hours=retention_hours),
        recent_results_limit=limit,
    )


def _coerce_app_config(config: Mapping[str, Any] | AppConfig | None) -> AppConfig:
    if isinstance(config, AppConfig):
        return config
    if isinstance(config, Mapping):
        return AppConfig(**dict(config))
    return AppConfig.build_default()


def _get_engine(dsn: str) -> Engine:
    engine = _ENGINE_CACHE.get(dsn)
    if engine is None:
        engine = create_engine(dsn, future=True)
        _ENGINE_CACHE[dsn] = engine
    return engine


def _stats_config_from_app_config(app_config: AppConfig) -> _StatsCacheConfig:
    return _StatsCacheConfig(
        slot_ttl=timedelta(seconds=app_config.stats_slot_cache_ttl_seconds),
        global_ttl=timedelta(seconds=app_config.stats_global_cache_ttl_seconds),
        recent_results_retention=timedelta(
            hours=app_config.stats_recent_results_retention_hours
        ),
        recent_results_limit=app_config.stats_recent_results_limit,
    )


def load_stats_cache_settings(
    config: Mapping[str, Any] | AppConfig | None = None,
    *,
    config_path: Path | None = None,
) -> _StatsCacheConfig:
    """Return cache settings for statistics services."""

    if config is not None:
        app_config = _coerce_app_config(config)
        return _stats_config_from_app_config(app_config)
    if config_path is not None:
        return _load_stats_cache_config(config_path)
    return _stats_config_from_app_config(AppConfig.build_default())


def build_service_registry(
    *,
    provider_factories: Mapping[str, PluginFactory] | None = None,
    service_overrides: Mapping[PluginKey, PluginFactory] | None = None,
    provider_config_path: Path | None = None,
) -> ServiceRegistry:
    """Construct a :class:`ServiceRegistry` with supplied factories.

    The default implementation keeps the registry minimal: it loads provider
    metadata from ``configs/providers.json`` (or a custom path) and registers
    factories supplied via ``provider_factories``. Concrete infrastructure
    components can be injected using ``service_overrides`` which mirrors the
    plugin keys declared on :class:`ServiceRegistry`.
    """

    registry = ServiceRegistry()

    config_path = provider_config_path or Path("configs/providers.json")
    for provider_id, config in _load_provider_configs(config_path).items():
        registry.register_provider_config(provider_id, config)

    def _stats_repository_factory(*, config: Mapping[str, Any] | AppConfig | None = None) -> object:
        app_config = _coerce_app_config(config)
        engine = _get_engine(app_config.database_url)
        return SqlAlchemyStatsRepository(engine)

    def _stats_service_factory(*, config: Mapping[str, Any] | AppConfig | None = None) -> object:
        repository = _stats_repository_factory(config=config)
        app_config = _coerce_app_config(config)
        stats_config = load_stats_cache_settings(app_config)
        return CachedStatsService(
            repository,
            slot_ttl=stats_config.slot_ttl,
            global_ttl=stats_config.global_ttl,
            recent_results_retention=stats_config.recent_results_retention,
            recent_results_limit=stats_config.recent_results_limit,
        )

    def _unit_of_work_factory(*, config: Mapping[str, Any] | AppConfig | None = None) -> object:
        app_config = _coerce_app_config(config)
        engine = _get_engine(app_config.database_url)
        return SqlAlchemyUnitOfWork(engine)

    registry.register_stats_repository(_stats_repository_factory)
    registry.register_stats_service(_stats_service_factory)
    registry.register_unit_of_work(_unit_of_work_factory)

    if provider_factories:
        for provider_id, factory in provider_factories.items():
            registry.register_provider_adapter(provider_id, factory)

    if service_overrides:
        for key, factory in service_overrides.items():
            registry.register(key, factory)

    return registry
