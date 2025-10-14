"""Service composition helpers."""

from __future__ import annotations

from .registry import ServiceRegistry


def build_service_registry() -> ServiceRegistry:
    """Construct a :class:`ServiceRegistry` with concrete factories.

    The implementation will wire repositories (PostgreSQL queue, media storage),
    provider adapters (Gemini, Turbotext) and domain services. Each dependency
    should respect TTL constraints described in the SDD (``T_sync_response`` for
    queue deadlines, ``T_result_retention`` for result storage) and rely on the
    infrastructure adapters added in this phase. Future iterations will provide
    concrete factory implementations.
    """

    raise NotImplementedError
