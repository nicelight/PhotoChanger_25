"""Реестр доменных сервисов и точек расширения.

Это единая точка, через которую тонкие фасады получают доступ
к провайдерам, очередям и хранилищам. Реализация подключаема
через плагины, определённые в ``src/app/plugins``.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, Mapping

from ..plugins.base import PluginFactory, PluginKey


@dataclass(slots=True)
class ServiceRegistry:
    """Простейший реестр фабрик доменных сервисов."""

    plugins: Dict[PluginKey, PluginFactory] = field(default_factory=dict)

    def register(self, key: PluginKey, factory: PluginFactory) -> None:
        """Регистрирует фабрику сервиса или адаптера."""

        self.plugins[key] = factory

    def resolve(self, key: PluginKey) -> PluginFactory:
        """Возвращает фабрику сервиса, описанную плагином."""

        return self.plugins[key]

    def snapshot(self) -> Mapping[PluginKey, PluginFactory]:
        """Иммутабельный снимок зарегистрированных плагинов."""

        return dict(self.plugins)
