from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import JSON

from app.db.base import Base

json_type = JSON().with_variant(JSONB, "postgresql")


class GraphNotification(Base):
    __tablename__ = "graph_notifications"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subscription_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    change_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    resource: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    client_state: Mapped[str | None] = mapped_column(String(255), nullable=True)
    tenant_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    raw_payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())


class AppSetting(Base):
    __tablename__ = "app_settings"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


class TeamsMessage(Base):
    __tablename__ = "teams_messages"
    __table_args__ = (UniqueConstraint("external_message_id", name="uq_teams_messages_external_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_message_id: Mapped[str] = mapped_column(String(255), nullable=False)
    sender_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    sender_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    channel_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    message_text: Mapped[str] = mapped_column(Text, nullable=False)
    raw_payload: Mapped[dict] = mapped_column(json_type, nullable=False)
    is_relevant: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    conversation_type: Mapped[str | None] = mapped_column(String(32), nullable=True)
    team_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    chat_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    parent_message_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    triage_result: Mapped["TriageResult | None"] = relationship(back_populates="message", uselist=False)


class TriageResult(Base):
    __tablename__ = "triage_results"
    __table_args__ = (UniqueConstraint("message_id", name="uq_triage_results_message_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    message_id: Mapped[int] = mapped_column(ForeignKey("teams_messages.id", ondelete="CASCADE"), nullable=False)
    category: Mapped[str] = mapped_column(String(64), nullable=False)
    priority: Mapped[str] = mapped_column(String(32), nullable=False)
    confidence: Mapped[float] = mapped_column(Float, nullable=False)
    summary: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_action: Mapped[str] = mapped_column(Text, nullable=False)
    suggested_reply: Mapped[str] = mapped_column(Text, nullable=False)
    needs_human_approval: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    message: Mapped[TeamsMessage] = relationship(back_populates="triage_result")
    approval_request: Mapped["ApprovalRequest | None"] = relationship(back_populates="triage_result", uselist=False)
    sent_reply: Mapped["SentReply | None"] = relationship(back_populates="triage_result", uselist=False)


class ApprovalRequest(Base):
    __tablename__ = "approval_requests"
    __table_args__ = (UniqueConstraint("triage_result_id", name="uq_approval_requests_triage_result_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    triage_result_id: Mapped[int] = mapped_column(ForeignKey("triage_results.id", ondelete="CASCADE"), nullable=False)
    telegram_chat_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    telegram_message_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    decided_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    triage_result: Mapped[TriageResult] = relationship(back_populates="approval_request")


class SentReply(Base):
    __tablename__ = "sent_replies"
    __table_args__ = (UniqueConstraint("triage_result_id", name="uq_sent_replies_triage_result_id"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    triage_result_id: Mapped[int] = mapped_column(ForeignKey("triage_results.id", ondelete="CASCADE"), nullable=False)
    target_channel: Mapped[str] = mapped_column(String(255), nullable=False)
    target_thread_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    final_reply_text: Mapped[str] = mapped_column(Text, nullable=False)
    delivery_status: Mapped[str] = mapped_column(String(32), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())

    triage_result: Mapped[TriageResult] = relationship(back_populates="sent_reply")
