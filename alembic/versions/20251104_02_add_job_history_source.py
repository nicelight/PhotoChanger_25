"""Add job_history.source column."""

from __future__ import annotations

from alembic import op
import sqlalchemy as sa


revision = "20251104_02"
down_revision = "20251104_01"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "job_history",
        sa.Column("source", sa.String(length=32), nullable=False, server_default="ingest"),
    )
    op.execute("UPDATE job_history SET source = 'ingest' WHERE source IS NULL")
    op.alter_column("job_history", "source", server_default=None)


def downgrade() -> None:
    op.drop_column("job_history", "source")
