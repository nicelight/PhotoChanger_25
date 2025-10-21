"""Alembic environment for PhotoChanger database migrations."""

from __future__ import annotations

from logging.config import fileConfig
from typing import Iterable

from alembic import context
from sqlalchemy import engine_from_config, pool

from src.app.db.models import Base as AdminBase
from src.app.infrastructure.queue import schema as queue_schema

config = context.config

if config.config_file_name is not None:
    fileConfig(config.config_file_name)

TARGET_METADATA: Iterable = (AdminBase.metadata, queue_schema.metadata)


def run_migrations_offline() -> None:
    """Run migrations in 'offline' mode."""

    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=TARGET_METADATA,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    """Run migrations in 'online' mode."""

    connectable = engine_from_config(
        config.get_section(config.config_ini_section),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=TARGET_METADATA)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
