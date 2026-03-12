from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, Float, ForeignKey, Integer, String, Text, UniqueConstraint, func
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


class Organization(Base):
    __tablename__ = "organizations"
    __table_args__ = (UniqueConstraint("slug", name="uq_organizations_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    billing_email: Mapped[str | None] = mapped_column(String(255), nullable=True)
    plan_tier: Mapped[str] = mapped_column(String(32), nullable=False, default="starter")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    projects: Mapped[list["Project"]] = relationship(back_populates="organization")


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (UniqueConstraint("slug", name="uq_projects_slug"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    organization_id: Mapped[int | None] = mapped_column(ForeignKey("organizations.id", ondelete="SET NULL"), nullable=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(255), nullable=False)
    ownership_type: Mapped[str] = mapped_column(String(32), nullable=False, default="company")
    summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    primary_repo_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="active")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    organization: Mapped[Organization | None] = relationship(back_populates="projects")
    settings: Mapped[list["ProjectSetting"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    integrations: Mapped[list["ProjectIntegration"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    people: Mapped[list["ProjectPerson"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    context_entries: Mapped[list["ProjectContextEntry"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    context_documents: Mapped[list["ProjectContextDocument"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    sync_jobs: Mapped[list["ProjectSyncJob"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    assistant_profiles: Mapped[list["AssistantProfile"]] = relationship(back_populates="project", cascade="all, delete-orphan")
    communication_style_rules: Mapped[list["CommunicationStyleRule"]] = relationship(
        back_populates="project",
        cascade="all, delete-orphan",
    )


class ProjectSetting(Base):
    __tablename__ = "project_settings"
    __table_args__ = (UniqueConstraint("project_id", "key", name="uq_project_settings_project_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    key: Mapped[str] = mapped_column(String(255), nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="settings")


class ProjectIntegration(Base):
    __tablename__ = "project_integrations"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    integration_type: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    external_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    base_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    config_json: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="integrations")


class ProjectPerson(Base):
    __tablename__ = "project_people"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    role_title: Mapped[str | None] = mapped_column(String(255), nullable=True)
    relationship_type: Mapped[str | None] = mapped_column(String(64), nullable=True)
    external_ref: Mapped[str | None] = mapped_column(String(255), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="people")
    communication_style_rules: Mapped[list["CommunicationStyleRule"]] = relationship(back_populates="person")


class ProjectContextEntry(Base):
    __tablename__ = "project_context_entries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    section: Mapped[str] = mapped_column(String(128), nullable=False, default="general")
    content: Mapped[str] = mapped_column(Text, nullable=False)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    source_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="context_entries")


class ProjectContextDocument(Base):
    __tablename__ = "project_context_documents"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str | None] = mapped_column(String(128), nullable=True)
    size_bytes: Mapped[int | None] = mapped_column(Integer, nullable=True)
    checksum: Mapped[str | None] = mapped_column(String(128), nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="upload")
    source_ref: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    extracted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="context_documents")


class ProjectSyncJob(Base):
    __tablename__ = "project_sync_jobs"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    job_type: Mapped[str] = mapped_column(String(64), nullable=False)
    status: Mapped[str] = mapped_column(String(32), nullable=False, default="queued")
    requested_by: Mapped[str | None] = mapped_column(String(128), nullable=True)
    payload: Mapped[dict] = mapped_column(json_type, nullable=False, default=dict)
    result_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="sync_jobs")


class AssistantProfile(Base):
    __tablename__ = "assistant_profiles"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mission: Mapped[str | None] = mapped_column(Text, nullable=True)
    tone_profile: Mapped[str | None] = mapped_column(Text, nullable=True)
    response_constraints: Mapped[str | None] = mapped_column(Text, nullable=True)
    escalation_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_language: Mapped[str] = mapped_column(String(16), nullable=False, default="tr")
    execution_mode: Mapped[str] = mapped_column(String(32), nullable=False, default="draft-first")
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="assistant_profiles")


class CommunicationStyleRule(Base):
    __tablename__ = "communication_style_rules"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    project_id: Mapped[int] = mapped_column(ForeignKey("projects.id", ondelete="CASCADE"), nullable=False)
    person_id: Mapped[int | None] = mapped_column(ForeignKey("project_people.id", ondelete="SET NULL"), nullable=True)
    channel_type: Mapped[str] = mapped_column(String(64), nullable=False)
    audience_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    audience_role: Mapped[str | None] = mapped_column(String(255), nullable=True)
    style_summary: Mapped[str] = mapped_column(Text, nullable=False)
    do_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    dont_guidance: Mapped[str | None] = mapped_column(Text, nullable=True)
    sample_reply: Mapped[str | None] = mapped_column(Text, nullable=True)
    source_type: Mapped[str] = mapped_column(String(64), nullable=False, default="manual")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    project: Mapped[Project] = relationship(back_populates="communication_style_rules")
    person: Mapped[ProjectPerson | None] = relationship(back_populates="communication_style_rules")


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



