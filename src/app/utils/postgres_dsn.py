"""Helpers for dealing with PostgreSQL DSN formats."""

from __future__ import annotations

from collections import OrderedDict
from dataclasses import dataclass
from typing import Any, Mapping, TYPE_CHECKING

try:  # pragma: no cover - optional dependency during import
    from sqlalchemy.engine import URL as _SQLAlchemyURL, make_url as _make_url
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    _SQLAlchemyURL = None  # type: ignore[assignment]
    _make_url = None  # type: ignore[assignment]
    _SQLALCHEMY_IMPORT_ERROR = exc
else:  # pragma: no cover - import succeeds under normal conditions
    _SQLALCHEMY_IMPORT_ERROR = None

try:  # pragma: no cover - optional dependency during import
    from psycopg import conninfo as _psycopg_conninfo
except ModuleNotFoundError as exc:  # pragma: no cover - optional dependency
    _psycopg_conninfo = None  # type: ignore[assignment]
    _PSYCOPG_IMPORT_ERROR = exc
else:  # pragma: no cover - import succeeds under normal conditions
    _PSYCOPG_IMPORT_ERROR = None

if TYPE_CHECKING:  # pragma: no cover - typing only
    from sqlalchemy.engine import URL
else:  # pragma: no cover - fallback when SQLAlchemy missing at runtime
    URL = Any  # type: ignore[assignment]


@dataclass(frozen=True)
class NormalizedPostgresDsn:
    """Container holding PostgreSQL DSN representations."""

    libpq: str
    sqlalchemy: str


_LIBPQ_KEYS = ("host", "port", "dbname", "user", "password")


def _require_conninfo() -> Any:
    if _psycopg_conninfo is None:
        raise ModuleNotFoundError(
            "psycopg is required for PostgreSQL DSN normalization"
        ) from _PSYCOPG_IMPORT_ERROR
    return _psycopg_conninfo


def _require_sqlalchemy_url() -> Any:
    if _SQLAlchemyURL is None:
        raise ModuleNotFoundError(
            "SQLAlchemy is required for PostgreSQL DSN normalization"
        ) from _SQLALCHEMY_IMPORT_ERROR
    return _SQLAlchemyURL


def _require_make_url() -> Any:
    if _make_url is None:
        raise ModuleNotFoundError(
            "SQLAlchemy is required for PostgreSQL DSN normalization"
        ) from _SQLALCHEMY_IMPORT_ERROR
    return _make_url


def _coerce_port(value: str | int | None) -> int | None:
    if value in (None, ""):
        return None
    if isinstance(value, int):
        return value
    try:
        return int(value)
    except (TypeError, ValueError) as exc:  # pragma: no cover - defensive
        raise ValueError(f"Invalid PostgreSQL port value: {value!r}") from exc


def _normalize_drivername(drivername: str | None) -> str:
    if not drivername or drivername == "postgresql":
        return "postgresql+psycopg"
    return drivername


def _libpq_from_url(url: URL) -> str:
    conninfo = _require_conninfo()
    params: "OrderedDict[str, object]" = OrderedDict()
    if getattr(url, "host", None):
        params["host"] = url.host  # type: ignore[index]
    if getattr(url, "port", None) is not None:
        params["port"] = str(url.port)  # type: ignore[index]
    if getattr(url, "database", None):
        params["dbname"] = url.database  # type: ignore[index]
    if getattr(url, "username", None):
        params["user"] = url.username  # type: ignore[index]
    if getattr(url, "password", None):
        params["password"] = url.password  # type: ignore[index]
    for key, value in getattr(url, "query", {}).items():
        if value is None:
            continue
        params[str(key)] = str(value)
    return conninfo.make_conninfo(**params)


def _url_from_libpq(mapping: Mapping[str, str]) -> URL:
    url_class = _require_sqlalchemy_url()
    query = {k: v for k, v in mapping.items() if k not in _LIBPQ_KEYS}
    port = _coerce_port(mapping.get("port")) if "port" in mapping else None
    return url_class.create(
        drivername="postgresql+psycopg",
        username=mapping.get("user") or None,
        password=mapping.get("password") or None,
        host=mapping.get("host") or None,
        port=port,
        database=mapping.get("dbname") or None,
        query=query,
    )


def _libpq_string_from_mapping(mapping: Mapping[str, str]) -> str:
    conninfo = _require_conninfo()
    params: "OrderedDict[str, str]" = OrderedDict()
    for key in _LIBPQ_KEYS:
        value = mapping.get(key)
        if value:
            params[key] = value
    for key, value in mapping.items():
        if key in _LIBPQ_KEYS or not value:
            continue
        params[key] = value
    return conninfo.make_conninfo(**params)


def normalize_postgres_dsn(raw_dsn: str) -> NormalizedPostgresDsn:
    """Return canonical PostgreSQL DSNs for psycopg and SQLAlchemy."""

    raw = raw_dsn.strip()
    if not raw:
        raise ValueError("PostgreSQL DSN must be a non-empty string")

    make_url = _require_make_url()

    if "://" in raw:
        url = make_url(raw)
        url = url.set(drivername=_normalize_drivername(url.drivername))
        libpq = _libpq_from_url(url)
        sqlalchemy = url.render_as_string(hide_password=False)
        return NormalizedPostgresDsn(libpq=libpq, sqlalchemy=sqlalchemy)

    conninfo = _require_conninfo()
    mapping = conninfo.conninfo_to_dict(raw)
    url = _url_from_libpq(mapping)
    libpq = _libpq_string_from_mapping(mapping)
    sqlalchemy = url.render_as_string(hide_password=False)
    return NormalizedPostgresDsn(libpq=libpq, sqlalchemy=sqlalchemy)


__all__ = ["NormalizedPostgresDsn", "normalize_postgres_dsn"]
