"""Turbotext provider adapter stubs.

Turbotext integration relies on polling API ``api_ai`` using ``queueid``
within ``T_sync_response``. The brief highlights that the provider accepts
public HTTPS links to images (`image/jpeg`, `image/png`, `image/webp`)
registered through PhotoChanger's temporary storage. The worker must stop
polling and cancel the task once the global deadline expires. This module
only defines the adapter scaffold for future implementations.
"""

from __future__ import annotations

from typing import Any, Mapping

from ..domain import Job, Slot
from .base import ProviderAdapter


class TurbotextProviderAdapter(ProviderAdapter):
    """Adapter skeleton for Turbotext queue-based API."""

    provider_id = "turbotext"

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
