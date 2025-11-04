"""Abstract provider driver definition."""

from abc import ABC, abstractmethod
from dataclasses import dataclass

from ..ingest.ingest_models import JobContext


@dataclass(slots=True)
class ProviderResult:
    """Standard response from provider drivers."""

    payload: bytes
    content_type: str


class ProviderDriver(ABC):
    """Base interface for provider drivers."""

    @abstractmethod
    async def process(self, job: JobContext) -> ProviderResult:
        """Process job and return payload with its content type."""
