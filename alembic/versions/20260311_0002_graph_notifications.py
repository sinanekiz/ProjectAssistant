from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260311_0002"
down_revision = "20260311_0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "graph_notifications",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("subscription_id", sa.String(length=255), nullable=True),
        sa.Column("change_type", sa.String(length=64), nullable=True),
        sa.Column("resource", sa.String(length=1024), nullable=True),
        sa.Column("client_state", sa.String(length=255), nullable=True),
        sa.Column("tenant_id", sa.String(length=255), nullable=True),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("graph_notifications")
