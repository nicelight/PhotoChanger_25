"""Unit-of-work protocol used to coordinate transactional operations."""

from __future__ import annotations

from typing import Protocol


class UnitOfWork(Protocol):
    """Represents an atomic transactional boundary."""

    def __enter__(self) -> UnitOfWork:
        """Enter the transactional context."""

        raise NotImplementedError

    def __exit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        tb: object,
    ) -> None:
        """Exit the transactional context, rolling back if needed."""

        raise NotImplementedError

    def commit(self) -> None:
        """Commit the current transaction."""

        raise NotImplementedError

    def rollback(self) -> None:
        """Rollback the current transaction."""

        raise NotImplementedError
