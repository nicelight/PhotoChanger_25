"""PhotoChanger application skeleton.

Все реализации должны ссылаться на спецификации в ``spec/contracts``
и оставаться максимально тонкими фасадами поверх доменных сервисов.
"""

from .api.facade import ApiFacade
from .services.registry import ServiceRegistry

__all__ = ["ApiFacade", "ServiceRegistry"]
