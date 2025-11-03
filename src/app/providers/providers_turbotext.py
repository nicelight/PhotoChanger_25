"""Turbotext provider driver stub."""

from ..ingest.ingest_models import JobContext
from .base import ProviderDriver


class TurbotextDriver(ProviderDriver):
    """Call Turbotext API (placeholder)."""

    async def process(self, job: JobContext) -> bytes:
        raise NotImplementedError
