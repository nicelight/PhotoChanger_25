"""PhotoChanger application skeleton.

Файл агрегирует базовые шаблоны приложения. Реализации должны ссылаться на
``spec/contracts`` и ``spec/docs/blueprints`` и оставаться максимально
тонкими фасадами поверх доменных сервисов.
"""

from functools import wraps

from .services.registry import ServiceRegistry

try:
    from .api.facade import ApiFacade
except ModuleNotFoundError as exc:  # pragma: no cover - optional FastAPI dependency
    if exc.name != "fastapi":
        raise
    ApiFacade = None  # type: ignore[assignment]

try:
    from .ui import UiFacade
except ModuleNotFoundError as exc:  # pragma: no cover - optional FastAPI dependency
    if exc.name != "fastapi":
        raise
    UiFacade = None  # type: ignore[assignment]

try:  # pragma: no cover - optional dependency used only in tests
    from fastapi.testclient import TestClient as _FastAPITestClient
except ModuleNotFoundError:  # pragma: no cover - FastAPI not installed
    _FastAPITestClient = None  # type: ignore[assignment]
else:  # pragma: no cover - exercised in contract/unit tests
    if not getattr(_FastAPITestClient, "_photochanger_allow_redirects", False):
        original_request = _FastAPITestClient.request
        original_get = _FastAPITestClient.get

        @wraps(original_request)
        def _patched_request(self, method, url, *args, **kwargs):
            if "allow_redirects" in kwargs and "follow_redirects" not in kwargs:
                kwargs["follow_redirects"] = kwargs.pop("allow_redirects")
            return original_request(self, method, url, *args, **kwargs)

        @wraps(original_get)
        def _patched_get(self, url, *args, allow_redirects=None, **kwargs):
            if (
                allow_redirects is not None
                and "follow_redirects" not in kwargs
            ):
                kwargs["follow_redirects"] = allow_redirects
            return original_get(self, url, *args, **kwargs)

        _FastAPITestClient.request = _patched_request  # type: ignore[assignment]
        _FastAPITestClient.get = _patched_get  # type: ignore[assignment]
        _FastAPITestClient._photochanger_allow_redirects = True  # type: ignore[attr-defined]

__all__ = ["ApiFacade", "UiFacade", "ServiceRegistry"]
