"""GPT Image 1.5 provider driver implementation."""

from __future__ import annotations

import asyncio
import logging
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
class GptImage15Driver(ProviderDriver):
    """Call GPT Image API (edits) with base64 output."""

    media_repo: MediaObjectRepository
    api_url: str = "https://api.openai.com/v1/images/edits"
    timeout_seconds: float = 30.0
    log: logging.Logger = field(default_factory=lambda: logger)

    async def process(self, job: JobContext) -> ProviderResult:
        self.log.info(
            "gptimage.request.start",
            extra={"slot_id": job.slot_id, "job_id": job.job_id},
        )

        settings = job.slot_settings or {}
        prompt = settings.get("prompt")
        if not prompt:
            raise ProviderExecutionError(
                "GPT Image prompt is required in slot settings"
            )

        model = settings.get("model", "gpt-image-1.5-2025-12-16")
        output = settings.get("output") or {}
        output_format = output.get("format", "png")
        output_compression = output.get("compression")
        size = output.get("size")
        retry_cfg = settings.get("retry_policy") or {}
        max_attempts = max(1, min(int(retry_cfg.get("max_attempts", 1)), 3))
        backoff_seconds = float(retry_cfg.get("backoff_seconds", 2.0))
        template_bindings = settings.get("template_media") or []

        payload_path = job.temp_payload_path
        if payload_path is None or not payload_path.exists():
            raise ProviderExecutionError("Ingest payload file is missing")

        ingest_bytes = payload_path.read_bytes()
        ingest_mime = (job.upload.content_type if job.upload else None) or _guess_mime(
            payload_path
        )

        try:
            resolved_templates = resolve_template_media(
                slot_id=job.slot_id,
                bindings=template_bindings,
                media_repo=self.media_repo,
            )
        except TemplateMediaResolutionError as exc:
            raise ProviderExecutionError(str(exc)) from exc

        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise ProviderExecutionError(
                "Environment variable OPENAI_API_KEY is not set"
            )

        headers = {"Authorization": f"Bearer {api_key}"}

        data: dict[str, Any] = {
            "model": model,
            "prompt": prompt,
        }
        if output_format:
            data["output_format"] = output_format
        if output_compression is not None:
            data["output_compression"] = output_compression
        if size:
            data["size"] = size

        files = _build_files(
            ingest_bytes=ingest_bytes,
            ingest_mime=ingest_mime,
            ingest_name=payload_path.name,
            templates=resolved_templates,
        )

        self.log.info(
            "gptimage.request.payload_meta "
            f"slot_id={job.slot_id} job_id={job.job_id} "
            f"payload_bytes={len(ingest_bytes)} payload_mime={ingest_mime} "
            f"template_count={len(resolved_templates)} prompt_len={len(prompt or '')}"
        )

        response = await self._send_request(
            headers=headers,
            data=data,
            files=files,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            slot_id=job.slot_id,
            job_id=job.job_id,
            model=model,
        )

        payload, content_type = _parse_response(response, output_format=output_format)
        self.log.info(
            "gptimage.request.success",
            extra={"slot_id": job.slot_id, "job_id": job.job_id},
        )
        return ProviderResult(payload=payload, content_type=content_type)

    async def _post(
        self,
        *,
        headers: dict[str, str],
        data: dict[str, Any],
        files: list[tuple[str, tuple[str, bytes, str]]],
    ) -> httpx.Response:
        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            return await client.post(
                self.api_url,
                headers=headers,
                data=data,
                files=files,
            )

    async def _send_request(
        self,
        *,
        headers: dict[str, str],
        data: dict[str, Any],
        files: list[tuple[str, tuple[str, bytes, str]]],
        max_attempts: int,
        backoff_seconds: float,
        slot_id: str,
        job_id: str | None,
        model: str,
    ) -> httpx.Response:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await self._post(headers=headers, data=data, files=files)
            except httpx.HTTPError as exc:
                if attempt >= max_attempts:
                    raise ProviderExecutionError(
                        f"GPT Image HTTP error: {exc}"
                    ) from exc
                await asyncio.sleep(backoff_seconds)
                continue

            if response.status_code == 200:
                return response

            if response.status_code not in {429, 500, 503} or attempt >= max_attempts:
                detail = _extract_error(response)
                body_preview = response.text[:500]
                self.log.error(
                    "gptimage.response.error status=%s detail=%s body_preview=%s",
                    response.status_code,
                    detail,
                    body_preview,
                    extra={
                        "slot_id": slot_id,
                        "job_id": job_id,
                        "provider": "gpt-image-1.5",
                        "model": model,
                        "http_status": response.status_code,
                        "provider_error_message": detail,
                    },
                )
                raise ProviderExecutionError(
                    f"GPT Image request failed (status={response.status_code}): {detail}"
                )

            await asyncio.sleep(backoff_seconds)

        raise ProviderExecutionError("GPT Image request failed after retries")


def _build_files(
    *,
    ingest_bytes: bytes,
    ingest_mime: str,
    ingest_name: str,
    templates: list[Any],
) -> list[tuple[str, tuple[str, bytes, str]]]:
    files: list[tuple[str, tuple[str, bytes, str]]] = []
    files.append(("image[]", (ingest_name or "ingest.png", ingest_bytes, ingest_mime)))
    for idx, template in enumerate(templates, start=1):
        filename = Path(template.path).name if getattr(template, "path", None) else ""
        name = filename or f"template-{idx}.png"
        data = _decode_template_bytes(template)
        files.append(("image[]", (name, data, template.mime_type)))
    return files


def _decode_template_bytes(template: Any) -> bytes:
    data_base64 = getattr(template, "data_base64", None)
    if isinstance(data_base64, str) and data_base64:
        import base64

        return base64.b64decode(data_base64)
    path = getattr(template, "path", None)
    if path:
        return Path(path).read_bytes()
    raise ProviderExecutionError("Template media bytes are missing")


def _parse_response(
    response: httpx.Response, *, output_format: str
) -> tuple[bytes, str]:
    try:
        data = response.json()
    except ValueError as exc:  # pragma: no cover - fallback
        raise ProviderExecutionError("GPT Image response is not valid JSON") from exc
    payloads = data.get("data") or []
    if not payloads:
        raise ProviderExecutionError("GPT Image response missing data")
    first = payloads[0]
    b64_json = first.get("b64_json")
    if not b64_json:
        raise ProviderExecutionError("GPT Image response missing b64_json")
    try:
        import base64

        payload = base64.b64decode(b64_json)
    except (ValueError, TypeError) as exc:
        raise ProviderExecutionError("GPT Image response payload is invalid") from exc
    return payload, _content_type_for_format(output_format)


def _content_type_for_format(output_format: str | None) -> str:
    fmt = (output_format or "png").lower()
    if fmt == "jpeg":
        return "image/jpeg"
    if fmt == "webp":
        return "image/webp"
    return "image/png"


def _extract_error(response: httpx.Response) -> str:
    try:
        data = response.json()
    except ValueError:  # pragma: no cover - fallback
        return response.text
    error = data.get("error")
    if isinstance(error, dict):
        message = (error.get("message") or "").strip()
        err_type = (error.get("type") or "").strip()
        return " ".join(part for part in (err_type, message) if part)
    return str(data)


def _guess_mime(path: Path) -> str:
    import mimetypes

    mime, _ = mimetypes.guess_type(path.name)
    return mime or "image/png"
