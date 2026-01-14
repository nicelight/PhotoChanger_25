"""Factory for provider drivers."""

from ..repositories.media_object_repository import MediaObjectRepository
from .providers_base import ProviderDriver
from .providers_gemini import GeminiDriver
from .providers_gemini_3_pro import Gemini3ProDriver
from .providers_gpt_image_1_5 import GptImage15Driver
from .providers_turbotext import TurbotextDriver


def create_driver(
    name: str, *, media_repo: MediaObjectRepository | None = None
) -> ProviderDriver:
    """Instantiate provider driver by name."""
    lower = name.lower()
    if lower == "gemini":
        if media_repo is None:
            raise ValueError("media_repo is required to instantiate GeminiDriver")
        return GeminiDriver(media_repo=media_repo)
    if lower in {"gemini-3-pro", "gemini-3-pro-image-preview"}:
        if media_repo is None:
            raise ValueError("media_repo is required to instantiate Gemini3ProDriver")
        return Gemini3ProDriver(media_repo=media_repo)
    if lower in {"gpt-image-1.5", "gpt-image-1.5-2025-12-16"}:
        if media_repo is None:
            raise ValueError("media_repo is required to instantiate GptImage15Driver")
        return GptImage15Driver(media_repo=media_repo)
    if lower == "turbotext":
        if media_repo is None:
            raise ValueError("media_repo is required to instantiate TurbotextDriver")
        return TurbotextDriver(media_repo=media_repo)
    raise ValueError(f"Unsupported provider '{name}'")
