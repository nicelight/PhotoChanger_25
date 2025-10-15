"""Реестр доменных сервисов и точек расширения.

Шаблон описывает минимальный контракт, через который фасады и адаптеры
получают доступ к инфраструктуре. Конкретные категории плагинов
перечислены в ``spec/docs/blueprints/context.md``: провайдеры AI,
очереди, хранилища, интеграции. Реализация по-прежнему загружается
через фабрики из ``src/app/plugins``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import ClassVar, Dict, Mapping

from ..plugins.base import PluginFactory, PluginKey


@dataclass(slots=True)
class ServiceRegistry:
    """Простейший реестр фабрик доменных сервисов и адаптеров."""

    JOB_SERVICE: ClassVar[PluginKey] = "service.job"
    SLOT_SERVICE: ClassVar[PluginKey] = "service.slot"
    SETTINGS_SERVICE: ClassVar[PluginKey] = "service.settings"
    MEDIA_SERVICE: ClassVar[PluginKey] = "service.media"
    STATS_SERVICE: ClassVar[PluginKey] = "service.stats"

    JOB_REPOSITORY: ClassVar[PluginKey] = "repository.job"
    SLOT_REPOSITORY: ClassVar[PluginKey] = "repository.slot"
    SETTINGS_REPOSITORY: ClassVar[PluginKey] = "repository.settings"
    MEDIA_STORAGE: ClassVar[PluginKey] = "storage.media"
    TEMPLATE_STORAGE: ClassVar[PluginKey] = "storage.template"
    STATS_REPOSITORY: ClassVar[PluginKey] = "repository.stats"
    UNIT_OF_WORK: ClassVar[PluginKey] = "unit_of_work"

    plugins: Dict[PluginKey, PluginFactory] = field(default_factory=dict)
    provider_factories: Dict[str, PluginFactory] = field(default_factory=dict)
    provider_configs: Dict[str, Mapping[str, object]] = field(default_factory=dict)

    def register(self, key: PluginKey, factory: PluginFactory) -> None:
        """Регистрирует фабрику сервиса или адаптера."""

        self.plugins[key] = factory

    def register_job_service(self, factory: PluginFactory) -> None:
        self.register(self.JOB_SERVICE, factory)

    def register_slot_service(self, factory: PluginFactory) -> None:
        self.register(self.SLOT_SERVICE, factory)

    def register_settings_service(self, factory: PluginFactory) -> None:
        self.register(self.SETTINGS_SERVICE, factory)

    def register_media_service(self, factory: PluginFactory) -> None:
        self.register(self.MEDIA_SERVICE, factory)

    def register_stats_service(self, factory: PluginFactory) -> None:
        self.register(self.STATS_SERVICE, factory)

    def register_job_repository(self, factory: PluginFactory) -> None:
        self.register(self.JOB_REPOSITORY, factory)

    def register_slot_repository(self, factory: PluginFactory) -> None:
        self.register(self.SLOT_REPOSITORY, factory)

    def register_settings_repository(self, factory: PluginFactory) -> None:
        self.register(self.SETTINGS_REPOSITORY, factory)

    def register_media_storage(self, factory: PluginFactory) -> None:
        self.register(self.MEDIA_STORAGE, factory)

    def register_template_storage(self, factory: PluginFactory) -> None:
        self.register(self.TEMPLATE_STORAGE, factory)

    def register_stats_repository(self, factory: PluginFactory) -> None:
        self.register(self.STATS_REPOSITORY, factory)

    def register_unit_of_work(self, factory: PluginFactory) -> None:
        """Register a factory producing ``UnitOfWork`` implementations."""

        self.register(self.UNIT_OF_WORK, factory)

    def register_provider_adapter(
        self, provider_id: str, factory: PluginFactory
    ) -> None:
        """Register a provider adapter factory keyed by ``provider_id``."""

        self.provider_factories[provider_id] = factory

    def register_provider_config(
        self, provider_id: str, config: Mapping[str, object]
    ) -> None:
        """Store provider metadata loaded from configuration files."""

        self.provider_configs[provider_id] = dict(config)

    def resolve_job_service(self) -> PluginFactory:
        return self.resolve(self.JOB_SERVICE)

    def resolve_slot_service(self) -> PluginFactory:
        return self.resolve(self.SLOT_SERVICE)

    def resolve_settings_service(self) -> PluginFactory:
        return self.resolve(self.SETTINGS_SERVICE)

    def resolve_media_service(self) -> PluginFactory:
        return self.resolve(self.MEDIA_SERVICE)

    def resolve_stats_service(self) -> PluginFactory:
        return self.resolve(self.STATS_SERVICE)

    def resolve_job_repository(self) -> PluginFactory:
        return self.resolve(self.JOB_REPOSITORY)

    def resolve_slot_repository(self) -> PluginFactory:
        return self.resolve(self.SLOT_REPOSITORY)

    def resolve_settings_repository(self) -> PluginFactory:
        return self.resolve(self.SETTINGS_REPOSITORY)

    def resolve_media_storage(self) -> PluginFactory:
        return self.resolve(self.MEDIA_STORAGE)

    def resolve_template_storage(self) -> PluginFactory:
        return self.resolve(self.TEMPLATE_STORAGE)

    def resolve_stats_repository(self) -> PluginFactory:
        return self.resolve(self.STATS_REPOSITORY)

    def resolve_unit_of_work(self) -> PluginFactory:
        return self.resolve(self.UNIT_OF_WORK)

    def resolve(self, key: PluginKey) -> PluginFactory:
        """Возвращает фабрику сервиса, описанную плагином."""

        return self.plugins[key]

    def resolve_provider_adapter(self, provider_id: str) -> PluginFactory:
        """Return the factory registered for ``provider_id``."""

        return self.provider_factories[provider_id]

    def resolve_provider_config(self, provider_id: str) -> Mapping[str, object]:
        """Return metadata associated with ``provider_id``."""

        return self.provider_configs.get(provider_id, {})

    def snapshot(self) -> Mapping[PluginKey, PluginFactory]:
        """Иммутабельный снимок зарегистрированных плагинов."""

        return dict(self.plugins)

    def provider_snapshot(self) -> Mapping[str, PluginFactory]:
        """Immutable snapshot of registered provider factories."""

        return dict(self.provider_factories)
