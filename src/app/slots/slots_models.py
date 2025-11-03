"""Slot domain dataclass."""

from dataclasses import dataclass


@dataclass(slots=True)
class Slot:
    id: str
    provider: str
    size_limit_mb: int
    is_active: bool = True
