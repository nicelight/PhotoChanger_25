"""Utilities for merging slot template media bindings."""

from __future__ import annotations

from collections import OrderedDict
from typing import Any, Iterable


def _normalize_entry(
    entry: dict[str, Any], *, default_role: str | None = None
) -> dict[str, Any]:
    """Return a shallow copy with normalized strings and defaulted role."""
    media_kind = entry.get("media_kind")
    media_object_id = entry.get("media_object_id")
    if not media_kind or not media_object_id:
        raise ValueError("template_media entry must include media_kind and media_object_id")
    normalized = dict(entry)
    normalized["media_kind"] = str(media_kind)
    normalized["media_object_id"] = str(media_object_id)
    if normalized.get("role") is None and default_role is not None:
        normalized["role"] = default_role
    return normalized


def merge_template_media(
    base: Iterable[dict[str, Any]],
    overrides: Iterable[dict[str, Any]],
    *,
    default_role: str | None = None,
) -> list[dict[str, Any]]:
    """
    Merge template_media bindings by media_kind without deleting existing entries.

    - Base entries are preserved as-is.
    - Overrides with the same media_kind update media_object_id; role is kept from base
      when present, otherwise taken from override or default_role.
    - Overrides with new media_kind are appended.
    """
    result: list[dict[str, Any]] = []
    index: OrderedDict[str, int] = OrderedDict()

    for entry in base:
        try:
            normalized = _normalize_entry(entry, default_role=default_role)
        except ValueError:
            continue
        result.append(normalized)
        index[normalized["media_kind"]] = len(result) - 1

    for entry in overrides:
        normalized = _normalize_entry(entry, default_role=default_role)
        kind = normalized["media_kind"]
        if kind in index:
            idx = index[kind]
            merged = dict(result[idx])
            merged["media_object_id"] = normalized["media_object_id"]
            if merged.get("role") is None and normalized.get("role") is not None:
                merged["role"] = normalized["role"]
            result[idx] = merged
        else:
            index[kind] = len(result)
            result.append(normalized)

    return result


def template_media_map(entries: Iterable[dict[str, Any]]) -> dict[str, str]:
    """Build a media_kind -> media_object_id map from merged template_media entries."""
    mapping: dict[str, str] = {}
    for entry in entries:
        media_kind = entry.get("media_kind")
        media_object_id = entry.get("media_object_id")
        if media_kind and media_object_id:
            mapping[str(media_kind)] = str(media_object_id)
    return mapping

