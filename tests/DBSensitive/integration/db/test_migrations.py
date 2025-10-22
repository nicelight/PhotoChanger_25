"""Smoke tests for Alembic migrations covering admin schema tables."""

from __future__ import annotations

from pathlib import Path

import pytest
from alembic import command
from alembic.config import Config

from src.app.utils.postgres_dsn import normalize_postgres_dsn

psycopg = pytest.importorskip(
    "psycopg", reason="psycopg is required for database migration tests"
)

PROJECT_ROOT = Path(__file__).resolve().parents[4]


@pytest.mark.integration
@pytest.mark.postgres
def test_upgrade_head_creates_admin_tables(postgres_dsn: str) -> None:
    """Upgrade to head and verify key tables, indexes and constraints exist."""

    normalized = normalize_postgres_dsn(postgres_dsn)
    config = Config(str(PROJECT_ROOT / "alembic.ini"))
    config.set_main_option("script_location", str(PROJECT_ROOT / "alembic"))
    config.set_main_option("sqlalchemy.url", normalized.sqlalchemy)

    # Reset to a clean slate before applying head migrations.
    command.downgrade(config, "base")
    command.upgrade(config, "head")

    expected_tables = {
        "admin_settings",
        "slots",
        "slot_templates",
        "processing_log_aggregates",
        "jobs",
        "processing_logs",
    }

    with psycopg.connect(normalized.libpq) as conn:
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT tablename
                FROM pg_tables
                WHERE schemaname = 'public'
                """
            )
            tables = {row[0] for row in cur.fetchall()}

        missing = expected_tables - tables
        assert not missing, f"tables missing after migration: {sorted(missing)}"

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT indexname
                FROM pg_indexes
                WHERE schemaname = 'public' AND tablename = 'slots'
                """
            )
            slot_indexes = {row[0] for row in cur.fetchall()}
        assert {
            "ix_slots_provider_operation",
            "ix_slots_updated_at",
        }.issubset(slot_indexes)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'slot_templates'::regclass
                  AND contype = 'u'
                """
            )
            slot_template_constraints = {row[0] for row in cur.fetchall()}
        assert "uq_slot_templates_slot_key" in slot_template_constraints

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT column_name
                FROM information_schema.columns
                WHERE table_name = 'admin_settings'
                """
            )
            admin_setting_columns = {row[0] for row in cur.fetchall()}
        assert {"etag", "updated_at", "is_secret"}.issubset(admin_setting_columns)

        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT conname
                FROM pg_constraint
                WHERE conrelid = 'processing_log_aggregates'::regclass
                  AND contype = 'c'
                """
            )
            aggregate_checks = {row[0] for row in cur.fetchall()}
        assert "ck_processing_log_aggregates_period" in aggregate_checks
