"""PhotoChanger application skeleton.

Файл агрегирует базовые шаблоны приложения. Реализации должны ссылаться на
``spec/contracts`` и ``spec/docs/blueprints`` и оставаться максимально
тонкими фасадами поверх доменных сервисов.
"""

from .api.facade import ApiFacade
from .services.registry import ServiceRegistry

__all__ = ["ApiFacade", "ServiceRegistry"]
