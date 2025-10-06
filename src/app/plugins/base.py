"""Базовые интерфейсы для плагинов PhotoChanger.

Плагины описывают расширяемые части платформы: провайдеры AI,
очереди, хранилища и внешние интеграции. Конкретные реализации
должны следовать контрактам, описанным в ``spec/contracts``.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable, TypeAlias

PluginKey: TypeAlias = str


@runtime_checkable
class PluginFactory(Protocol):
    """Фабрика, создающая конкретную реализацию сервиса."""

    def __call__(self, *, config: dict | None = None) -> object:
        """Возвращает инициализированный сервис или адаптер."""
