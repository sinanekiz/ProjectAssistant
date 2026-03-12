from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "20260312_0007"
down_revision = "20260312_0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "organizations",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("name", sa.String(length=255), nullable=False),
        sa.Column("slug", sa.String(length=255), nullable=False),
        sa.Column("owner_name", sa.String(length=255), nullable=True),
        sa.Column("billing_email", sa.String(length=255), nullable=True),
        sa.Column("plan_tier", sa.String(length=32), nullable=False, server_default="starter"),
        sa.Column("summary", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=32), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("slug", name="uq_organizations_slug"),
    )

    op.add_column("projects", sa.Column("organization_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_projects_organization_id_organizations",
        "projects",
        "organizations",
        ["organization_id"],
        ["id"],
        ondelete="SET NULL",
    )

    op.create_table(
        "assistant_profiles",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("display_name", sa.String(length=255), nullable=False),
        sa.Column("mission", sa.Text(), nullable=True),
        sa.Column("tone_profile", sa.Text(), nullable=True),
        sa.Column("response_constraints", sa.Text(), nullable=True),
        sa.Column("escalation_policy", sa.Text(), nullable=True),
        sa.Column("default_language", sa.String(length=16), nullable=False, server_default="tr"),
        sa.Column("execution_mode", sa.String(length=32), nullable=False, server_default="draft-first"),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )

    op.create_table(
        "communication_style_rules",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("project_id", sa.Integer(), sa.ForeignKey("projects.id", ondelete="CASCADE"), nullable=False),
        sa.Column("person_id", sa.Integer(), sa.ForeignKey("project_people.id", ondelete="SET NULL"), nullable=True),
        sa.Column("channel_type", sa.String(length=64), nullable=False),
        sa.Column("audience_name", sa.String(length=255), nullable=True),
        sa.Column("audience_role", sa.String(length=255), nullable=True),
        sa.Column("style_summary", sa.Text(), nullable=False),
        sa.Column("do_guidance", sa.Text(), nullable=True),
        sa.Column("dont_guidance", sa.Text(), nullable=True),
        sa.Column("sample_reply", sa.Text(), nullable=True),
        sa.Column("source_type", sa.String(length=64), nullable=False, server_default="manual"),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )


def downgrade() -> None:
    op.drop_table("communication_style_rules")
    op.drop_table("assistant_profiles")
    op.drop_constraint("fk_projects_organization_id_organizations", "projects", type_="foreignkey")
    op.drop_column("projects", "organization_id")
    op.drop_table("organizations")
