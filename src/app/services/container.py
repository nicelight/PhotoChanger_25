"""Service composition helpers."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Mapping

from ..plugins.base import PluginFactory, PluginKey
from .registry import ServiceRegistry


def _load_provider_configs(config_path: Path) -> Mapping[str, Mapping[str, object]]:
    if not config_path.exists():
        return {}
    with config_path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    providers = raw.get("providers", [])
    mapping: dict[str, Mapping[str, object]] = {}
    for entry in providers:
        provider_id = entry.get("id")
        if not provider_id:
            continue
        mapping[str(provider_id)] = dict(entry)
    return mapping


def build_service_registry(
    *,
    provider_factories: Mapping[str, PluginFactory] | None = None,
    service_overrides: Mapping[PluginKey, PluginFactory] | None = None,
    provider_config_path: Path | None = None,
) -> ServiceRegistry:
    """Construct a :class:`ServiceRegistry` with supplied factories.

    The default implementation keeps the registry minimal: it loads provider
    metadata from ``configs/providers.json`` (or a custom path) and registers
    factories supplied via ``provider_factories``. Concrete infrastructure
    components can be injected using ``service_overrides`` which mirrors the
    plugin keys declared on :class:`ServiceRegistry`.
    """

    registry = ServiceRegistry()

    config_path = provider_config_path or Path("configs/providers.json")
    for provider_id, config in _load_provider_configs(config_path).items():
        registry.register_provider_config(provider_id, config)

    if provider_factories:
        for provider_id, factory in provider_factories.items():
            registry.register_provider_adapter(provider_id, factory)

    if service_overrides:
        for key, factory in service_overrides.items():
            registry.register(key, factory)

    return registry
