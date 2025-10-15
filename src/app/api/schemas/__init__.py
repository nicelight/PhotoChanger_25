"""Exports of Pydantic schemas mirroring ``spec/contracts/schemas``."""

from . import models
from .models import *  # noqa: F401,F403 - re-export contract models

__all__ = models.__all__


def _rebuild_models() -> None:
    for name in __all__:
        attr = getattr(models, name, None)
        rebuild = getattr(attr, "model_rebuild", None)
        if callable(rebuild):
            rebuild()


_rebuild_models()
