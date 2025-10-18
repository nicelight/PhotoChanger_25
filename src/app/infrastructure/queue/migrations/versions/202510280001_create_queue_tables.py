"""Create jobs and processing_logs tables."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "202510280001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)

    if not inspector.has_table("jobs"):
        op.create_table(
            "jobs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("slot_id", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column(
                "is_finalized",
                sa.Boolean(),
                nullable=False,
                server_default=sa.text("FALSE"),
            ),
            sa.Column("failure_reason", sa.Text(), nullable=True),
            sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("finalized_at", sa.DateTime(timezone=True), nullable=True),
            sa.Column("payload_path", sa.Text(), nullable=True),
            sa.Column("provider_job_reference", sa.Text(), nullable=True),
            sa.Column("result_file_path", sa.Text(), nullable=True),
            sa.Column("result_inline_base64", sa.Text(), nullable=True),
            sa.Column("result_mime_type", sa.Text(), nullable=True),
            sa.Column("result_size_bytes", sa.BigInteger(), nullable=True),
            sa.Column("result_checksum", sa.Text(), nullable=True),
            sa.Column("result_expires_at", sa.DateTime(timezone=True), nullable=True),
        )

    inspector = sa.inspect(bind)

    existing_job_indexes = (
        {index["name"] for index in inspector.get_indexes("jobs")}
        if inspector.has_table("jobs")
        else set()
    )
    if "ix_jobs_status_finalized_expires" not in existing_job_indexes:
        op.create_index(
            "ix_jobs_status_finalized_expires",
            "jobs",
            ["status", "is_finalized", "expires_at"],
        )
    if "ix_jobs_slot_created_at" not in existing_job_indexes:
        op.create_index(
            "ix_jobs_slot_created_at",
            "jobs",
            ["slot_id", "created_at"],
        )

    if not inspector.has_table("processing_logs"):
        op.create_table(
            "processing_logs",
            sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
            sa.Column("job_id", postgresql.UUID(as_uuid=True), nullable=False),
            sa.Column("slot_id", sa.Text(), nullable=False),
            sa.Column("status", sa.Text(), nullable=False),
            sa.Column("occurred_at", sa.DateTime(timezone=True), nullable=False),
            sa.Column("message", sa.Text(), nullable=True),
            sa.Column("details", postgresql.JSONB(astext_type=sa.Text()), nullable=True),
            sa.Column("provider_latency_ms", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["job_id"], ["jobs.id"], ondelete="CASCADE"),
        )

    inspector = sa.inspect(bind)

    existing_log_indexes = (
        {index["name"] for index in inspector.get_indexes("processing_logs")}
        if inspector.has_table("processing_logs")
        else set()
    )
    if "ix_processing_logs_job_occurred" not in existing_log_indexes:
        op.create_index(
            "ix_processing_logs_job_occurred",
            "processing_logs",
            ["job_id", "occurred_at"],
        )


def downgrade() -> None:
    op.drop_index("ix_processing_logs_job_occurred", table_name="processing_logs")
    op.drop_table("processing_logs")
    op.drop_index("ix_jobs_slot_created_at", table_name="jobs")
    op.drop_index("ix_jobs_status_finalized_expires", table_name="jobs")
    op.drop_table("jobs")
