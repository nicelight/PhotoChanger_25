"""Gemini provider driver implementation."""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import httpx

from ..ingest.ingest_errors import ProviderExecutionError
from ..ingest.ingest_models import JobContext
from ..repositories.media_object_repository import MediaObjectRepository
from .providers_base import ProviderDriver, ProviderResult
from .template_media_resolver import (
    TemplateMediaResolutionError,
    resolve_template_media,
)

logger = logging.getLogger(__name__)


@dataclass(slots=True)
class GeminiDriver(ProviderDriver):
    """Call Gemini API using a single universal method."""

    media_repo: MediaObjectRepository
    api_url_base: str = "https://generativelanguage.googleapis.com/v1beta"
    timeout_seconds: float = 30.0
    log: logging.Logger = field(default_factory=lambda: logger)

    async def process(self, job: JobContext) -> ProviderResult:
        self.log.info(
            "gemini.request.start",
            extra={"slot_id": job.slot_id, "job_id": job.job_id},
        )

        settings = job.slot_settings or {}
        prompt = settings.get("prompt")
        if not prompt:
            raise ProviderExecutionError("Gemini prompt is required in slot settings")

        model = settings.get("model", "gemini-2.5-flash-image")
        output = (settings.get("output") or {}).get("mime_type", "image/png")
        retry_cfg = settings.get("retry_policy") or {}
        max_attempts = max(1, min(int(retry_cfg.get("max_attempts", 1)), 3))
        backoff_seconds = float(retry_cfg.get("backoff_seconds", 2.0))
        safety_settings = settings.get("safety_settings")
        template_bindings = settings.get("template_media") or []

        payload_path = job.temp_payload_path
        if payload_path is None or not payload_path.exists():
            raise ProviderExecutionError("Ingest payload file is missing")

        ingest_bytes = payload_path.read_bytes()
        ingest_mime = (job.upload.content_type if job.upload else None) or _guess_mime(
            payload_path
        )
        ingest_inline = {
            "mime_type": ingest_mime,
            "data": base64.b64encode(ingest_bytes).decode("ascii"),
        }

        try:
            resolved_templates = resolve_template_media(
                slot_id=job.slot_id,
                bindings=template_bindings,
                media_repo=self.media_repo,
            )
        except TemplateMediaResolutionError as exc:
            raise ProviderExecutionError(str(exc)) from exc

        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ProviderExecutionError(
                "Environment variable GEMINI_API_KEY is not set"
            )

        url = f"{self.api_url_base}/models/{model}:generateContent"
        headers = {
            "x-goog-api-key": api_key,
            "Content-Type": "application/json",
        }

        parts = [{"inline_data": ingest_inline}]
        for template in resolved_templates:
            parts.append(
                {
                    "inline_data": {
                        "mime_type": template.mime_type,
                        "data": template.data_base64,
                    }
                }
            )
        parts.append({"text": prompt})

        body: dict[str, Any] = {
            "model": model,
            "contents": [
                {
                    "role": "user",
                    "parts": parts,
                }
            ],
        }
        if output:
            body["generationConfig"] = {"responseMimeType": output}
        if safety_settings:
            body["safetySettings"] = safety_settings

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                if attempt >= max_attempts:
                    raise ProviderExecutionError(f"Gemini HTTP error: {exc}") from exc
                await asyncio.sleep(backoff_seconds)
                continue

            if response.status_code == 200:
                result = self._parse_response(
                    response.json(), fallback_mime=(output or ingest_mime)
                )
                self.log.info(
                    "gemini.request.success",
                    extra={"slot_id": job.slot_id, "job_id": job.job_id},
                )
                return result

            if not self._should_retry(response) or attempt >= max_attempts:
                error_detail = _extract_error(response)
                raise ProviderExecutionError(
                    f"Gemini request failed (status={response.status_code}): {error_detail}"
                )

            await asyncio.sleep(backoff_seconds)

        raise ProviderExecutionError("Gemini request failed after retries")

    async def _post(
        self, url: str, *, headers: dict[str, str], json: dict[str, Any]
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            return await client.post(url, headers=headers, json=json)

    def _should_retry(self, response: httpx.Response) -> bool:
        try:
            data = response.json()
        except ValueError:  # pragma: no cover - fallback
            return response.status_code in {429, 500, 503}
        error = data.get("error")
        if not isinstance(error, dict):
            return response.status_code in {429, 500, 503}
        status = error.get("status", "").upper()
        return status in {"RESOURCE_EXHAUSTED", "DEADLINE_EXCEEDED"}

    def _parse_response(
        self, data: dict[str, Any], *, fallback_mime: str
    ) -> ProviderResult:
        candidates = data.get("candidates") or []
        text_messages: list[str] = []
        finish_reasons: list[str] = []

        for candidate in candidates:
            if reason := candidate.get("finishReason"):
                finish_reasons.append(reason)

            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                inline = part.get("inline_data")
                if inline and inline.get("data"):
                    mime = inline.get("mime_type") or fallback_mime
                    try:
                        payload = base64.b64decode(inline["data"])
                    except (KeyError, ValueError) as exc:
                        raise ProviderExecutionError(
                            "Gemini response payload is invalid"
                        ) from exc
                    return ProviderResult(payload=payload, content_type=mime)

                if text := part.get("text"):
                    text_messages.append(text)

        error_msg = "Gemini response does not contain inline data"
        details = []
        if finish_reasons:
            details.append(f"Reasons: {', '.join(finish_reasons)}")
        if text_messages:
            joined_text = "; ".join(text_messages)
            if len(joined_text) > 200:
                joined_text = joined_text[:197] + "..."
            details.append(f"Text: {joined_text}")

        if details:
            error_msg += f" ({', '.join(details)})"

        raise ProviderExecutionError(error_msg)


def _extract_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:  # pragma: no cover - fallback
        return response.text
    error = data.get("error")
    if isinstance(error, dict):
        message = (error.get("message") or "").strip()
        status = (error.get("status") or "").strip()
        return " ".join(part for part in (status, message) if part)
    return str(data)


def _guess_mime(path: Path) -> str:
    mime, _ = mimetypes.guess_type(path.name)
    return mime or "image/png"
