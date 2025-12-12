"""Gemini provider driver implementation."""

from __future__ import annotations

import asyncio
import base64
import logging
import mimetypes
import os
import json
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

        # По документации Gemini REST для Python используется inline_data/mime_type.
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
        # responseMimeType в Gemini предназначен только для текстовых форматов (JSON mode и т.п.);
        # для изображений его отправка приводит к INVALID_ARGUMENT.
        if output and output in {
            "text/plain",
            "application/json",
            "application/xml",
            "application/yaml",
            "text/x.enum",
        }:
            body["generationConfig"] = {"responseMimeType": output}
        if safety_settings:
            body["safetySettings"] = safety_settings

        self.log.info(
            "gemini.request.payload_meta "
            f"slot_id={job.slot_id} job_id={job.job_id} "
            f"payload_bytes={len(ingest_bytes)} payload_mime={ingest_mime} "
            f"template_count={len(resolved_templates)} prompt_len={len(prompt or '')}"
        )

        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post(url, headers=headers, json=body)
            except httpx.HTTPError as exc:
                if attempt >= max_attempts:
                    raise ProviderExecutionError(f"Gemini HTTP error: {exc}") from exc
                await asyncio.sleep(backoff_seconds)
                continue

            if response.status_code == 200:
                data = response.json()
                summary = _response_summary(data)
                self.log.info("gemini.response.received %s", summary)
                masked_body = _mask_inline_data(data)
                body_preview = json.dumps(masked_body, ensure_ascii=False)
                if len(body_preview) > 4000:
                    body_preview = body_preview[:4000] + "...(truncated)"
                self.log.info(
                    "gemini.response.body %s", body_preview, extra={"slot_id": job.slot_id, "job_id": job.job_id}
                )
                has_inline = _has_inline_data(data)
                if not has_inline:
                    # Попробуем вернуть читабельное сообщение провайдера вместо "502 Bad Gateway".
                    finish_reason = None
                    finish_message = None
                    try:
                        first_candidate = (data.get("candidates") or [None])[0] or {}
                        finish_reason = first_candidate.get("finishReason") or first_candidate.get("finish_reason")
                        finish_message = first_candidate.get("finishMessage") or first_candidate.get("finish_message")
                    except Exception:  # pragma: no cover - defensive
                        finish_reason = None
                        finish_message = None

                    self.log.warning(
                        "gemini.response.no_inline_data %s",
                        body_preview,
                        extra={"slot_id": job.slot_id, "job_id": job.job_id},
                    )
                    if finish_message:
                        raise ProviderExecutionError(finish_message)
                    if finish_reason:
                        raise ProviderExecutionError(f"Gemini response has no image (finish_reason={finish_reason})")
                result = self._parse_response(
                    data, fallback_mime=(output or ingest_mime)
                )
                self.log.info(
                    "gemini.request.success",
                    extra={"slot_id": job.slot_id, "job_id": job.job_id},
                )
                return result

            if not self._should_retry(response) or attempt >= max_attempts:
                error_detail = _extract_error(response)
                body_preview = response.text[:500]
                self.log.error(
                    "gemini.response.error status=%s detail=%s body_preview=%s",
                    response.status_code,
                    error_detail,
                    body_preview,
                    extra={
                        "slot_id": job.slot_id,
                        "job_id": job.job_id,
                        "status_code": response.status_code,
                        "error_detail": error_detail,
                        "body_preview": body_preview,
                    },
                )
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
        for candidate in candidates:
            content = candidate.get("content") or {}
            for part in content.get("parts", []):
                inline = part.get("inline_data") or part.get("inlineData")
                if inline and inline.get("data"):
                    mime = (
                        inline.get("mime_type")
                        or inline.get("mimeType")
                        or fallback_mime
                    )
                    try:
                        payload = base64.b64decode(inline["data"])
                    except (KeyError, ValueError) as exc:
                        raise ProviderExecutionError(
                            "Gemini response payload is invalid"
                        ) from exc
                    return ProviderResult(payload=payload, content_type=mime)
        raise ProviderExecutionError("Gemini response does not contain inline data")


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


def _has_inline_data(data: dict[str, Any]) -> bool:
    """Check whether Gemini response contains inline_data parts (metadata only, no payload)."""
    candidates = data.get("candidates") or []
    for candidate in candidates:
        content = candidate.get("content") or {}
        for part in content.get("parts", []):
            inline = part.get("inline_data") or part.get("inlineData")
            if inline and inline.get("data"):
                return True
    return False


def _mask_inline_data(obj: Any) -> Any:
    """Remove inline_data payloads to avoid logging base64 blobs."""
    if isinstance(obj, dict):
        result = {}
        for key, value in obj.items():
            if key in {"inline_data", "inlineData"} and isinstance(value, dict):
                # keep mime_type, drop data
                masked = {k: v for k, v in value.items() if k not in {"data", "data_base64"}}
                result[key] = masked
            else:
                result[key] = _mask_inline_data(value)
        return result
    if isinstance(obj, list):
        return [_mask_inline_data(item) for item in obj]
    return obj


def _response_summary(data: dict[str, Any]) -> str:
    candidates = data.get("candidates") or []
    first = candidates[0] if candidates else {}
    parts = (first.get("content") or {}).get("parts", [])
    part_types: list[str] = []
    text_preview = None
    for part in parts:
        if "inline_data" in part or "inlineData" in part:
            part_types.append("inline_data")
        if "text" in part:
            part_types.append("text")
            if text_preview is None:
                text_preview = part.get("text", "")
    preview_full = text_preview or ""
    preview = preview_full[:160]
    return (
        f"candidates={len(candidates)} "
        f"part_types={part_types} "
        f"has_inline_data={_has_inline_data(data)} "
        f"text_preview='{preview}' "
        f"text_len={len(preview_full)}"
    )
