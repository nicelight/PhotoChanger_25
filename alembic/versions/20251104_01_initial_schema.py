"""Initial database schema."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251104_01"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "slot",
        sa.Column("id", sa.String(length=32), primary_key=True),
        sa.Column(
            "display_name", sa.String(length=128), nullable=False, server_default=""
        ),
        sa.Column("provider", sa.String(length=64), nullable=False),
        sa.Column(
            "operation",
            sa.String(length=64),
            nullable=False,
            server_default="image_edit",
        ),
        sa.Column("settings_json", sa.Text(), nullable=False, server_default="{}"),
        sa.Column("size_limit_mb", sa.Integer(), nullable=False, server_default="15"),
        sa.Column(
            "is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")
        ),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("updated_by", sa.String(length=64)),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )

    op.create_table(
        "slot_template_media",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "slot_id",
            sa.String(length=32),
            sa.ForeignKey("slot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("media_kind", sa.String(length=32), nullable=False),
        sa.Column("media_object_id", sa.String(length=64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
    )
    op.create_index(
        "ix_slot_template_media_slot_id", "slot_template_media", ["slot_id"]
    )

    op.create_table(
        "job_history",
        sa.Column("job_id", sa.String(length=64), primary_key=True),
        sa.Column(
            "slot_id",
            sa.String(length=32),
            sa.ForeignKey("slot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("failure_reason", sa.String(length=64)),
        sa.Column(
            "started_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("sync_deadline", sa.DateTime()),
        sa.Column("completed_at", sa.DateTime()),
        sa.Column("result_path", sa.String(length=512)),
        sa.Column("result_expires_at", sa.DateTime()),
    )
    op.create_index("ix_job_history_slot_id", "job_history", ["slot_id"])

    op.create_table(
        "media_object",
        sa.Column("id", sa.String(length=64), primary_key=True),
        sa.Column(
            "job_id",
            sa.String(length=64),
            sa.ForeignKey("job_history.job_id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "slot_id",
            sa.String(length=32),
            sa.ForeignKey("slot.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("scope", sa.String(length=16), nullable=False),
        sa.Column("path", sa.String(length=512), nullable=False),
        sa.Column("preview_path", sa.String(length=512)),
        sa.Column("expires_at", sa.DateTime(), nullable=False),
        sa.Column("cleaned_at", sa.DateTime()),
    )
    op.create_index("ix_media_object_job_id", "media_object", ["job_id"])

    op.create_table(
        "settings",
        sa.Column("key", sa.String(length=64), primary_key=True),
        sa.Column("value", sa.Text(), nullable=False),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            nullable=False,
            server_default=sa.text("CURRENT_TIMESTAMP"),
        ),
        sa.Column("updated_by", sa.String(length=64)),
    )


def downgrade() -> None:
    op.drop_table("settings")
    op.drop_index("ix_media_object_job_id", table_name="media_object")
    op.drop_table("media_object")
    op.drop_index("ix_job_history_slot_id", table_name="job_history")
    op.drop_table("job_history")
    op.drop_index("ix_slot_template_media_slot_id", table_name="slot_template_media")
    op.drop_table("slot_template_media")
    op.drop_table("slot")
