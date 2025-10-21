"""Create admin settings, slots and aggregates."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202511010001"
down_revision = "202510280001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "admin_settings",
        sa.Column("key", sa.String(length=64), nullable=False),
        sa.Column("value", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
        sa.Column("value_type", sa.String(length=32), nullable=True),
        sa.Column("is_secret", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("etag", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.Column("updated_by", sa.String(length=64), nullable=True),
        sa.CheckConstraint("length(key) > 0", name="ck_admin_settings_key_length"),
        sa.PrimaryKeyConstraint("key", name="pk_admin_settings"),
    )
    op.create_index("ix_admin_settings_updated_at", "admin_settings", ["updated_at"])

    op.create_table(
        "slots",
        sa.Column("id", sa.String(length=16), nullable=False),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("provider_id", sa.String(length=64), nullable=False),
        sa.Column("operation_id", sa.String(length=64), nullable=False),
        sa.Column("settings_json", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("last_reset_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.Column("etag", sa.String(length=32), nullable=False),
        sa.CheckConstraint("id ~ '^slot-[0-9]{3}$'", name="ck_slots_id_format"),
        sa.PrimaryKeyConstraint("id", name="pk_slots"),
    )
    op.create_index("ix_slots_provider_operation", "slots", ["provider_id", "operation_id"])
    op.create_index("ix_slots_updated_at", "slots", ["updated_at"])

    op.create_table(
        "slot_templates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_id", sa.String(length=16), nullable=False),
        sa.Column("setting_key", sa.String(length=128), nullable=False),
        sa.Column("path", sa.Text(), nullable=False),
        sa.Column("mime", sa.String(length=128), nullable=False),
        sa.Column("size_bytes", sa.Integer(), nullable=False),
        sa.Column("checksum", sa.String(length=64), nullable=True),
        sa.Column("label", sa.String(length=128), nullable=True),
        sa.Column("uploaded_by", sa.String(length=64), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_slot_templates"),
        sa.UniqueConstraint("slot_id", "setting_key", name="uq_slot_templates_slot_key"),
    )
    op.create_index("ix_slot_templates_slot_id", "slot_templates", ["slot_id"])

    op.create_table(
        "processing_log_aggregates",
        sa.Column("id", postgresql.UUID(as_uuid=True), nullable=False),
        sa.Column("slot_id", sa.String(length=16), nullable=True),
        sa.Column("granularity", sa.String(length=8), nullable=False),
        sa.Column("period_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("period_end", sa.DateTime(timezone=True), nullable=False),
        sa.Column("success", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("timeouts", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("provider_errors", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("cancelled", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("errors", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("ingest_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
            server_onupdate=sa.func.now(),
        ),
        sa.CheckConstraint("period_end >= period_start", name="ck_processing_log_aggregates_period"),
        sa.ForeignKeyConstraint(["slot_id"], ["slots.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_processing_log_aggregates"),
    )
    op.create_index(
        "uq_processing_log_aggregates_scope_period",
        "processing_log_aggregates",
        [sa.text("COALESCE(slot_id, 'GLOBAL')"), "granularity", "period_start", "period_end"],
        unique=True,
    )
    op.create_index(
        "ix_processing_log_aggregates_slot_period",
        "processing_log_aggregates",
        ["slot_id", "period_start"],
    )
    op.create_index(
        "ix_processing_log_aggregates_period_end",
        "processing_log_aggregates",
        ["period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_processing_log_aggregates_period_end", table_name="processing_log_aggregates")
    op.drop_index("ix_processing_log_aggregates_slot_period", table_name="processing_log_aggregates")
    op.drop_index(
        "uq_processing_log_aggregates_scope_period",
        table_name="processing_log_aggregates",
    )
    op.drop_table("processing_log_aggregates")

    op.drop_index("ix_slot_templates_slot_id", table_name="slot_templates")
    op.drop_table("slot_templates")

    op.drop_index("ix_slots_updated_at", table_name="slots")
    op.drop_index("ix_slots_provider_operation", table_name="slots")
    op.drop_table("slots")

    op.drop_index("ix_admin_settings_updated_at", table_name="admin_settings")
    op.drop_table("admin_settings")
