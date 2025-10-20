"""PhotoChanger application skeleton.

Файл агрегирует базовые шаблоны приложения. Реализации должны ссылаться на
``spec/contracts`` и ``spec/docs/blueprints`` и оставаться максимально
тонкими фасадами поверх доменных сервисов.
"""

from functools import wraps
import inspect

from .api.facade import ApiFacade
from .ui import UiFacade
from .services.registry import ServiceRegistry

try:  # pragma: no cover - optional dependency used only in tests
    from fastapi.testclient import TestClient as _FastAPITestClient
except ModuleNotFoundError:  # pragma: no cover - FastAPI not installed
    _FastAPITestClient = None  # type: ignore[assignment]
else:  # pragma: no cover - exercised in contract/unit tests
    if not getattr(_FastAPITestClient, "_photochanger_allow_redirects", False):
        original_request = _FastAPITestClient.request
        original_get = _FastAPITestClient.get

        def _supports_kwarg(callable_obj, kwarg: str) -> bool:
            try:
                return kwarg in inspect.signature(callable_obj).parameters
            except (TypeError, ValueError):  # pragma: no cover - C extensions, etc.
                return False

        request_supports_follow_redirects = _supports_kwarg(
            original_request, "follow_redirects"
        )
        get_supports_follow_redirects = _supports_kwarg(
            original_get, "follow_redirects"
        )
        _sentinel = object()

        @wraps(original_request)
        def _patched_request(self, method, url, *args, **kwargs):
            if (
                "allow_redirects" in kwargs
                and "follow_redirects" not in kwargs
                and request_supports_follow_redirects
            ):
                kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
            return original_request(self, method, url, *args, **kwargs)

        @wraps(original_get)
        def _patched_get(self, url, *args, **kwargs):
            allow_redirects = kwargs.pop("allow_redirects", _sentinel)
            if allow_redirects is not _sentinel:
                target_kwarg = "allow_redirects"
                if (
                    "follow_redirects" not in kwargs
                    and get_supports_follow_redirects
                ):
                    target_kwarg = "follow_redirects"
                kwargs[target_kwarg] = allow_redirects
            return original_get(self, url, *args, **kwargs)

        _FastAPITestClient.request = _patched_request  # type: ignore[assignment]
        _FastAPITestClient.get = _patched_get  # type: ignore[assignment]
        _FastAPITestClient._photochanger_allow_redirects = True  # type: ignore[attr-defined]

__all__ = ["ApiFacade", "UiFacade", "ServiceRegistry"]
