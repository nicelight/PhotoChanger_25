"""HTTP API facades bound to ``spec/contracts/openapi.yaml``.

Фактические контроллеры должны генерироваться по контракту и учитывать
описанные сценарии из ``spec/docs/blueprints/use-cases.md``.
"""

from .facade import ApiFacade

__all__ = ["ApiFacade"]
