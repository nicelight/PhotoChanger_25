"""Statistics aggregation logic."""

from dataclasses import dataclass
from typing import Sequence


@dataclass(slots=True)
class StatsService:
    """Aggregate ingest statistics (stub)."""

    repo: "StatsRepository"

    def slot_metrics(self) -> Sequence[dict]:
        """Return basic metrics per slot."""
        return self.repo.slot_metrics()
