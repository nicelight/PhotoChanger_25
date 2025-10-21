"""Domain level exceptions and helpers for repository layers."""

from __future__ import annotations

from contextlib import contextmanager
from dataclasses import dataclass
from typing import Iterator

from sqlalchemy import exc as sa_exc

__all__ = [
    "AppError",
    "RepositoryError",
    "NotFoundError",
    "ETagMismatchError",
    "IntegrityConstraintViolation",
    "TemplateBindingError",
    "ArchivedEntityError",
    "DatabaseOperationError",
    "ensure_etag",
    "ensure_found",
    "verify_template_slot",
    "handle_sqlalchemy_errors",
]


class AppError(Exception):
    """Base class for application specific errors."""


class RepositoryError(AppError):
    """Base class for persistence layer failures."""


class NotFoundError(RepositoryError):
    """Raised when a record could not be located."""


class ETagMismatchError(RepositoryError):
    """Raised when optimistic locking preconditions fail."""


class IntegrityConstraintViolation(RepositoryError):
    """Raised when a database constraint is violated."""


class TemplateBindingError(IntegrityConstraintViolation):
    """Raised when template-slot relationships are invalid."""


class ArchivedEntityError(RepositoryError):
    """Raised when an archived record is modified without revival."""


class DatabaseOperationError(RepositoryError):
    """Raised for unexpected database errors."""


@dataclass(slots=True)
class _EntityContext:
    """Internal helper describing the entity for error messages."""

    entity: str | None = None

    def format(self, message: str) -> str:
        if self.entity:
            return f"{self.entity}: {message}"
        return message


def ensure_found(record: object | None, *, entity: str, identifier: str) -> object:
    """Ensure a record exists, otherwise raise :class:`NotFoundError`."""

    if record is None:
        raise NotFoundError(f"{entity} '{identifier}' not found")
    return record


def ensure_etag(*, expected: str, actual: str, entity: str) -> None:
    """Validate that the stored ETag matches the provided precondition."""

    if expected != actual:
        raise ETagMismatchError(f"{entity} precondition failed: expected {expected}, got {actual}")


def verify_template_slot(*, slot_id: str, template_slot_id: str) -> None:
    """Ensure template bindings are not cross-slot."""

    if slot_id != template_slot_id:
        raise TemplateBindingError(
            f"template belongs to slot '{template_slot_id}', cannot use with '{slot_id}'"
        )


def _translate_sqlalchemy_error(exc: Exception, *, context: _EntityContext) -> RepositoryError:
    if isinstance(exc, sa_exc.IntegrityError):
        return IntegrityConstraintViolation(context.format("integrity constraint violated"))
    if isinstance(exc, sa_exc.DBAPIError):
        return DatabaseOperationError(context.format("database operation failed"))
    return RepositoryError(context.format(str(exc)))


@contextmanager
def handle_sqlalchemy_errors(*, entity: str | None = None) -> Iterator[None]:
    """Translate SQLAlchemy errors into domain specific ones."""

    context = _EntityContext(entity)
    try:
        yield
    except (sa_exc.IntegrityError, sa_exc.DBAPIError) as exc:
        raise _translate_sqlalchemy_error(exc, context=context) from exc
