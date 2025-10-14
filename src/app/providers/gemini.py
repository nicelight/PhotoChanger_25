"""Gemini provider adapter stubs.

Gemini operations are described in ``Docs/brief.md`` and the provider
blueprints. The platform relies on model ``gemini-2.5-flash-image`` with
rate limits 500 RPS / 2 000 RPD and accepts images up to 2 GB with MIME
``image/png``, ``image/jpeg``, ``image/webp``, ``image/heic`` и
``image/heif``.  The actual HTTP integration will be implemented in later
phases; for now the adapter only defines the scaffold.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..domain import Job, Slot
from .base import ProviderAdapter


class GeminiProviderAdapter(ProviderAdapter):
    """Adapter skeleton for Google Gemini APIs."""

    provider_id = "gemini"

    def prepare_payload(
        self,
        *,
        job: Job,
        slot: Slot,
        settings: Mapping[str, Any],
        context: Mapping[str, Any],
    ) -> Mapping[str, Any]:
        raise NotImplementedError

    async def submit_job(self, payload: Mapping[str, Any]) -> str:
        raise NotImplementedError

    async def poll_status(self, reference: str) -> Mapping[str, Any]:
        raise NotImplementedError

    async def cancel(self, reference: str) -> None:
        raise NotImplementedError
