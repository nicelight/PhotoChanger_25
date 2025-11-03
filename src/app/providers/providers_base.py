"""Abstract provider driver definition."""

from abc import ABC, abstractmethod

from ..ingest.ingest_models import JobContext


class ProviderDriver(ABC):
    """Base interface for provider drivers."""

    @abstractmethod
    async def process(self, job: JobContext) -> bytes:
        """Process job and return binary result."""

