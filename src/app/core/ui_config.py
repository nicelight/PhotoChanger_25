"""Scaffolding for admin UI configuration loading."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Sequence


@dataclass(slots=True)
class ProviderOperationConfig:
    """Describes a single provider operation exposed to the UI."""

    id: str
    name: str
    needs: Sequence[str]
    schema_ref: str


@dataclass(slots=True)
class ProviderConfigEntry:
    """Static provider descriptor consumed by the admin UI."""

    id: str
    name: str
    requires_public_media: bool
    operations: Sequence[ProviderOperationConfig]


def load_provider_catalog(path: Path | None = None) -> Sequence[ProviderConfigEntry]:
    """Load ``configs/providers.json`` and return provider descriptors."""

    raise NotImplementedError


__all__ = [
    "ProviderConfigEntry",
    "ProviderOperationConfig",
    "load_provider_catalog",
]
