"""Интерфейсы и хелперы для плагинов PhotoChanger.

Сервисы, описанные в спецификациях (см. ``spec/docs/blueprints/context.md``),
подключаются именно через эти плагины. Файл служит отправной точкой для
реализации фабрик.
"""

from .base import PluginFactory, PluginKey

__all__ = ["PluginFactory", "PluginKey"]
