"""Base interfaces for AI provider adapters.

The blueprint documents describe two primary providers (Gemini and
Turbotext) and outline their limits, expected payload structures and
polling semantics.  Concrete adapters must follow these contracts while
keeping the implementation pluggable via ``ServiceRegistry`` factories.
This module exposes the abstract interface used by workers and services
that orchestrate provider calls.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any, Mapping

from ..domain import Job, Slot


class ProviderAdapter(ABC):
    """Abstract adapter that hides provider-specific integrations.

    Implementations are expected to:

    * respect ``T_sync_response`` when submitting and polling jobs;
    * prepare payloads according to operation metadata defined in
      ``spec/contracts/providers``;
    * surface provider identifiers (``queueid`` for Turbotext, response ids
      for Gemini) so workers can persist them in
      ``Job.provider_job_reference``;
    * cooperate with the media subsystem to honour TTL constraints from the
      SDD.
    """

    provider_id: str

    @abstractmethod
    def prepare_payload(
        self,
        *,
        job: Job,
        slot: Slot,
        settings: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        """Construct a provider-specific payload without performing I/O."""

    @abstractmethod
    async def submit_job(self, payload: Mapping[str, Any]) -> str:
        """Submit a prepared payload and return a provider job reference."""

    @abstractmethod
    async def poll_status(self, reference: str) -> Mapping[str, Any]:
        """Poll provider status for ``reference`` within ``T_sync_response``."""

    @abstractmethod
    async def cancel(self, reference: str) -> None:
        """Cancel provider processing when PhotoChanger finalises a job."""
