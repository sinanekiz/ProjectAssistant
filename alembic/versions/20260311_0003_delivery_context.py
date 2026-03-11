from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260311_0003"
down_revision = "20260311_0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("teams_messages", sa.Column("conversation_type", sa.String(length=32), nullable=True))
    op.add_column("teams_messages", sa.Column("team_id", sa.String(length=255), nullable=True))
    op.add_column("teams_messages", sa.Column("chat_id", sa.String(length=255), nullable=True))
    op.add_column("teams_messages", sa.Column("parent_message_id", sa.String(length=255), nullable=True))


def downgrade() -> None:
    op.drop_column("teams_messages", "parent_message_id")
    op.drop_column("teams_messages", "chat_id")
    op.drop_column("teams_messages", "team_id")
    op.drop_column("teams_messages", "conversation_type")
