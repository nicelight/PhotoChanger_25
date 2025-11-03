"""Gemini provider driver stub."""

from ..ingest.ingest_models import JobContext
from .base import ProviderDriver


class GeminiDriver(ProviderDriver):
    """Call Gemini API (placeholder)."""

    async def process(self, job: JobContext) -> bytes:
        raise NotImplementedError
