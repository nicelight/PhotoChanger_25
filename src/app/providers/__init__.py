"""Пакет для адаптеров AI-провайдеров, подключаемых как плагины."""

from .base import ProviderAdapter
from .gemini import GeminiProviderAdapter
from .turbotext import TurbotextProviderAdapter

__all__ = [
    "ProviderAdapter",
    "GeminiProviderAdapter",
    "TurbotextProviderAdapter",
]
