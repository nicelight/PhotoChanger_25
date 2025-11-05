"""Turbotext provider driver implementation."""

from __future__ import annotations

import asyncio
import logging
import os
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urljoin

import httpx

from ..ingest.ingest_errors import ProviderExecutionError
from ..ingest.ingest_models import JobContext
from ..media.public_media_links import build_public_media_url
from ..media.temp_media_store import TempMediaHandle
from ..repositories.media_object_repository import MediaObjectRepository
from .providers_base import ProviderDriver, ProviderResult

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class TurbotextDriver(ProviderDriver):
    """Call Turbotext API using polling."""

    media_repo: MediaObjectRepository
    api_endpoint: str = "https://www.turbotext.ru/api_ai/generate_image2image"
    timeout_seconds: float = 15.0
    poll_interval_seconds: float = 2.0
    max_attempts: int = 20
    log: logging.Logger = field(default_factory=lambda: logger)

    async def process(self, job: JobContext) -> ProviderResult:
        settings = job.slot_settings or {}
        prompt = settings.get("prompt")
        if not prompt:
            raise ProviderExecutionError("Turbotext prompt is required in slot settings")

        base_url = os.getenv("PUBLIC_MEDIA_BASE_URL")
        if not base_url:
            raise ProviderExecutionError("PUBLIC_MEDIA_BASE_URL is not configured")
        api_key = os.getenv("TURBOTEXT_API_KEY")
        if not api_key:
            raise ProviderExecutionError("TURBOTEXT_API_KEY is not set")

        ingest_handle = _select_ingest_handle(job.temp_media)
        if ingest_handle is None:
            raise ProviderExecutionError("Ingest media handle missing for Turbotext")

        ingest_url = build_public_media_url(base_url, ingest_handle.media_id)
        create_payload = self._build_create_payload(
            settings=settings,
            ingest_url=ingest_url,
            prompt=prompt,
            job=job,
            base_url=base_url,
        )

        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/x-www-form-urlencoded",
        }

        queue_id = await self._create_queue(headers=headers, data=create_payload)
        self.log.info(
            "turbotext.queue.created",
            extra={"slot_id": job.slot_id, "job_id": job.job_id, "queue_id": queue_id},
        )

        attempt = 0
        while attempt < self.max_attempts:
            attempt += 1
            await asyncio.sleep(self.poll_interval_seconds)
            result = await self._poll_result(headers=headers, queue_id=queue_id)

            if not result.get("success"):
                action = result.get("action")
                if action == "reconnect":
                    continue
                message = (result.get("error") or result.get("message") or "Unknown error")
                raise ProviderExecutionError(f"Turbotext reported failure: {message}")

            data = result.get("data") or {}
            uploaded_image = data.get("uploaded_image")
            if not uploaded_image:
                raise ProviderExecutionError("Turbotext result missing uploaded_image")
            payload_bytes, content_type = await self._download_file(uploaded_image, api_key=api_key)
            return ProviderResult(payload=payload_bytes, content_type=content_type)

        raise ProviderExecutionError("Turbotext polling exceeded maximum attempts")

    async def _create_queue(self, *, headers: dict[str, str], data: dict[str, Any]) -> str:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.api_endpoint, headers=headers, data=data)
        if response.status_code != 200:
            raise ProviderExecutionError(f"Turbotext create_queue failed with status {response.status_code}")
        body = response.json()
        if not body.get("success"):
            message = body.get("error") or body.get("message") or "Unknown error"
            raise ProviderExecutionError(f"Turbotext create_queue error: {message}")
        queue_id = body.get("queueid")
        if not queue_id:
            raise ProviderExecutionError("Turbotext did not return queueid")
        return str(queue_id)

    async def _poll_result(self, *, headers: dict[str, str], queue_id: str) -> dict[str, Any]:
        form = {"do": "get_result", "queueid": queue_id}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.post(self.api_endpoint, headers=headers, data=form)
        if response.status_code != 200:
            raise ProviderExecutionError(f"Turbotext get_result failed with status {response.status_code}")
        return response.json()

    async def _download_file(self, url: str, *, api_key: str) -> tuple[bytes, str]:
        full_url = url if url.startswith("http") else urljoin("https://www.turbotext.ru/", url.lstrip("/"))
        headers = {"Authorization": f"Bearer {api_key}"}
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            response = await client.get(full_url, headers=headers)
        if response.status_code != 200:
            raise ProviderExecutionError(f"Turbotext file download failed with status {response.status_code}")
        content_type = response.headers.get("Content-Type", "image/png")
        return response.content, content_type

    def _build_create_payload(
        self,
        *,
        settings: dict[str, Any],
        ingest_url: str,
        prompt: str,
        job: JobContext,
        base_url: str,
    ) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "do": "create_queue",
            "url": ingest_url,
            "content": prompt,
        }
        for field in ("strength", "scale", "negative_prompt", "user_id", "seed", "original_language"):
            if field in settings:
                payload[field] = settings[field]

        for entry in settings.get("template_media") or []:
            form_field = entry.get("form_field")
            if not form_field:
                continue

            media_id = entry.get("media_object_id")
            if not media_id and entry.get("media_kind"):
                try:
                    media = self.media_repo.get_media_by_kind(job.slot_id, entry["media_kind"])
                    media_id = media.id
                except (KeyError, ValueError):
                    if entry.get("optional"):
                        continue
                    raise ProviderExecutionError(
                        f"Turbotext template media not found for role '{entry.get('role')}'"
                    )

            if not media_id:
                if entry.get("optional"):
                    continue
                raise ProviderExecutionError(
                    f"Turbotext template media requires media_object_id or media_kind (role={entry.get('role')})"
                )

            payload[form_field] = build_public_media_url(base_url, media_id)

        return payload


def _select_ingest_handle(handles: list[TempMediaHandle]) -> TempMediaHandle | None:
    return handles[0] if handles else None
