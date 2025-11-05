"""Helpers for building public media URLs."""

from __future__ import annotations

from urllib.parse import urljoin


def build_public_media_url(base_url: str, media_id: str) -> str:
    base = base_url.rstrip("/") + "/"
    return urljoin(base, f"public/provider-media/{media_id}")
