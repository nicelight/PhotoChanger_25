"""Turbotext provider driver stub."""

from ..ingest.ingest_models import JobContext
from .providers_base import ProviderDriver, ProviderResult


class TurbotextDriver(ProviderDriver):
    """Call Turbotext API (placeholder)."""

    async def process(self, job: JobContext) -> ProviderResult:
        raise NotImplementedError
