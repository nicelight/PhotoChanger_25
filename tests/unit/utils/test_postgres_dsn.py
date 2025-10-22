from __future__ import annotations

import pytest

from src.app.utils.postgres_dsn import NormalizedPostgresDsn, normalize_postgres_dsn

pytest.importorskip(
    "psycopg", reason="psycopg is required for DSN normalization tests"
)
pytest.importorskip(
    "sqlalchemy", reason="SQLAlchemy is required for DSN normalization tests"
)


@pytest.mark.unit
def test_normalize_from_sqlalchemy_url() -> None:
    raw = "postgresql://user:pass@localhost:5432/photochanger?sslmode=require"

    normalized = normalize_postgres_dsn(raw)

    assert isinstance(normalized, NormalizedPostgresDsn)
    assert (
        normalized.sqlalchemy
        == "postgresql+psycopg://user:pass@localhost:5432/photochanger?sslmode=require"
    )
    expected_tokens = [
        "host=localhost",
        "port=5432",
        "dbname=photochanger",
        "user=user",
        "password=pass",
    ]
    assert normalized.libpq.split()[:5] == expected_tokens
    assert normalized.libpq.endswith("sslmode=require"), normalized.libpq


@pytest.mark.unit
def test_normalize_from_libpq_dsn() -> None:
    raw = (
        "host=localhost port=5432 dbname=photochanger user=user password=pass"
        " sslmode=require"
    )

    normalized = normalize_postgres_dsn(raw)

    assert (
        normalized.sqlalchemy
        == "postgresql+psycopg://user:pass@localhost:5432/photochanger?sslmode=require"
    )
    expected_tokens = [
        "host=localhost",
        "port=5432",
        "dbname=photochanger",
        "user=user",
        "password=pass",
    ]
    assert normalized.libpq.split()[:5] == expected_tokens
    assert normalized.libpq.endswith("sslmode=require"), normalized.libpq


@pytest.mark.unit
def test_normalize_preserves_explicit_driver() -> None:
    raw = "postgresql+asyncpg://user:pass@localhost:5432/photochanger"

    normalized = normalize_postgres_dsn(raw)

    assert (
        normalized.sqlalchemy
        == "postgresql+asyncpg://user:pass@localhost:5432/photochanger"
    )
    assert normalized.libpq.startswith("host=localhost")
