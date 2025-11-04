"""Factory for provider drivers."""

from .providers_base import ProviderDriver
from .providers_gemini import GeminiDriver
from .providers_turbotext import TurbotextDriver


def create_driver(name: str) -> ProviderDriver:
    """Instantiate provider driver by name."""
    drivers: dict[str, type[ProviderDriver]] = {
        "gemini": GeminiDriver,
        "turbotext": TurbotextDriver,
    }
    try:
        return drivers[name.lower()]()
    except KeyError as exc:
        raise ValueError(f"Unsupported provider '{name}'") from exc
