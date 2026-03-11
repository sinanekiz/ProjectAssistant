from __future__ import annotations

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision = "20260311_0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "teams_messages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("external_message_id", sa.String(length=255), nullable=False),
        sa.Column("sender_name", sa.String(length=255), nullable=True),
        sa.Column("sender_id", sa.String(length=255), nullable=True),
        sa.Column("channel_id", sa.String(length=255), nullable=True),
        sa.Column("channel_name", sa.String(length=255), nullable=True),
        sa.Column("thread_id", sa.String(length=255), nullable=True),
        sa.Column("message_text", sa.Text(), nullable=False),
        sa.Column("raw_payload", postgresql.JSONB(astext_type=sa.Text()), nullable=False),
        sa.Column("is_relevant", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("external_message_id", name="uq_teams_messages_external_message_id"),
    )

    op.create_table(
        "triage_results",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("message_id", sa.Integer(), sa.ForeignKey("teams_messages.id", ondelete="CASCADE"), nullable=False),
        sa.Column("category", sa.String(length=64), nullable=False),
        sa.Column("priority", sa.String(length=32), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("summary", sa.Text(), nullable=False),
        sa.Column("suggested_action", sa.Text(), nullable=False),
        sa.Column("suggested_reply", sa.Text(), nullable=False),
        sa.Column("needs_human_approval", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("message_id", name="uq_triage_results_message_id"),
    )

    op.create_table(
        "approval_requests",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("triage_result_id", sa.Integer(), sa.ForeignKey("triage_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("telegram_chat_id", sa.String(length=64), nullable=True),
        sa.Column("telegram_message_id", sa.String(length=64), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("decided_at", sa.DateTime(timezone=True), nullable=True),
        sa.UniqueConstraint("triage_result_id", name="uq_approval_requests_triage_result_id"),
    )

    op.create_table(
        "sent_replies",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("triage_result_id", sa.Integer(), sa.ForeignKey("triage_results.id", ondelete="CASCADE"), nullable=False),
        sa.Column("target_channel", sa.String(length=255), nullable=False),
        sa.Column("target_thread_id", sa.String(length=255), nullable=True),
        sa.Column("final_reply_text", sa.Text(), nullable=False),
        sa.Column("delivery_status", sa.String(length=32), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("triage_result_id", name="uq_sent_replies_triage_result_id"),
    )


def downgrade() -> None:
    op.drop_table("sent_replies")
    op.drop_table("approval_requests")
    op.drop_table("triage_results")
    op.drop_table("teams_messages")
