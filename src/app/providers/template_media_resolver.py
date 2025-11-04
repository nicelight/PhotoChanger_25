"""Utilities for resolving template media bindings for providers."""

from __future__ import annotations

import base64
import mimetypes
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

from ..repositories.media_object_repository import MediaObjectRepository


@dataclass(slots=True)
class TemplateBinding:
    """Configuration entry describing a template reference."""

    role: str
    media_kind: str | None = None
    media_object_id: str | None = None
    optional: bool = False


@dataclass(slots=True)
class ResolvedTemplateMedia:
    """Result of resolving a template binding."""

    role: str
    media_object_id: str
    media_kind: str | None
    path: Path
    mime_type: str
    data_base64: str


class TemplateMediaResolutionError(RuntimeError):
    """Base error raised when resolving template media fails."""


def _binding_from_dict(entry: dict) -> TemplateBinding:
    try:
        role = entry["role"]
    except KeyError as exc:  # pragma: no cover - defensive
        raise TemplateMediaResolutionError("Template media entry requires 'role' field") from exc

    return TemplateBinding(
        role=role,
        media_kind=entry.get("media_kind"),
        media_object_id=entry.get("media_object_id"),
        optional=bool(entry.get("optional", False)),
    )


def resolve_template_media(
    *,
    slot_id: str,
    bindings: Sequence[dict] | None,
    media_repo: MediaObjectRepository,
) -> list[ResolvedTemplateMedia]:
    """Resolve template media bindings into file payloads with base64 data."""
    if not bindings:
        return []

    resolved: list[ResolvedTemplateMedia] = []
    for raw in bindings:
        binding = _binding_from_dict(raw)
        media = _resolve_single_binding(slot_id=slot_id, binding=binding, media_repo=media_repo)
        if media is None:
            continue  # optional binding skipped
        resolved.append(media)
    return resolved


def _resolve_single_binding(
    *,
    slot_id: str,
    binding: TemplateBinding,
    media_repo: MediaObjectRepository,
) -> ResolvedTemplateMedia | None:
    media_object_id: str | None = None

    if binding.media_object_id:
        media_object_id = binding.media_object_id
    elif binding.media_kind:
        try:
            media = media_repo.get_media_by_kind(slot_id, binding.media_kind)
        except (KeyError, ValueError) as exc:
            if binding.optional:
                return None
            raise TemplateMediaResolutionError(str(exc)) from exc
        media_object_id = media.id
    else:
        raise TemplateMediaResolutionError(
            f"Template media '{binding.role}' must define 'media_object_id' or 'media_kind'"
        )

    try:
        media_obj = media_repo.get_media(media_object_id)
    except KeyError as exc:
        if binding.optional:
            return None
        raise TemplateMediaResolutionError(str(exc)) from exc

    path = media_obj.path
    if not path.exists():
        if binding.optional:
            return None
        raise TemplateMediaResolutionError(
            f"Template media file '{path}' for role '{binding.role}' is missing"
        )

    data = path.read_bytes()
    mime_type = mimetypes.guess_type(path.name)[0] or "image/png"
    encoded = base64.b64encode(data).decode("ascii")

    return ResolvedTemplateMedia(
        role=binding.role,
        media_object_id=media_object_id,
        media_kind=binding.media_kind,
        path=path,
        mime_type=mime_type,
        data_base64=encoded,
    )
