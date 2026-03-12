from __future__ import annotations

import json
import re
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AssistantProfile,
    CommunicationStyleRule,
    Organization,
    Project,
    ProjectContextEntry,
    ProjectIntegration,
    ProjectPerson,
    ProjectSetting,
)

_SLUG_RE = re.compile(r"[^a-z0-9]+")


@dataclass(slots=True)
class ProjectAssistantBrief:
    headline: str
    sections: list[tuple[str, list[str]]]

    @property
    def rendered(self) -> str:
        lines = [self.headline]
        for title, entries in self.sections:
            lines.append("")
            lines.append(f"[{title}]")
            if entries:
                lines.extend(f"- {entry}" for entry in entries)
            else:
                lines.append("- Henuz veri yok.")
        return "\n".join(lines)


@dataclass(slots=True)
class ProjectCreateResult:
    project: Project
    created: bool


def slugify_value(value: str) -> str:
    slug = _SLUG_RE.sub("-", value.strip().lower()).strip("-")
    return slug or "workspace"


_LOAD_OPTIONS = (
    selectinload(Project.organization),
    selectinload(Project.settings),
    selectinload(Project.integrations),
    selectinload(Project.people),
    selectinload(Project.context_entries),
    selectinload(Project.context_documents),
    selectinload(Project.sync_jobs),
    selectinload(Project.assistant_profiles),
    selectinload(Project.communication_style_rules).selectinload(CommunicationStyleRule.person),
)


def list_organizations(db: Session) -> list[Organization]:
    return list(db.scalars(select(Organization).order_by(Organization.created_at.desc())))


def get_organization(db: Session, organization_id: int) -> Organization | None:
    return db.scalar(select(Organization).where(Organization.id == organization_id))


def create_organization(
    db: Session,
    *,
    name: str,
    owner_name: str = "",
    billing_email: str = "",
    plan_tier: str = "starter",
    summary: str = "",
    status: str = "active",
) -> Organization:
    base_slug = slugify_value(name)
    slug = base_slug
    suffix = 2
    while db.scalar(select(Organization).where(Organization.slug == slug)) is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    organization = Organization(
        name=name.strip(),
        slug=slug,
        owner_name=owner_name.strip() or None,
        billing_email=billing_email.strip() or None,
        plan_tier=plan_tier.strip() or "starter",
        summary=summary.strip() or None,
        status=status.strip() or "active",
    )
    db.add(organization)
    db.commit()
    db.refresh(organization)
    return organization


def list_projects(db: Session) -> list[Project]:
    return list(db.scalars(select(Project).options(*_LOAD_OPTIONS).order_by(Project.created_at.desc())))


def get_project(db: Session, project_id: int) -> Project | None:
    return db.scalar(select(Project).options(*_LOAD_OPTIONS).where(Project.id == project_id))


def create_project(
    db: Session,
    *,
    organization: Organization | None,
    name: str,
    ownership_type: str,
    summary: str,
    primary_repo_path: str,
    status: str = "active",
) -> Project:
    base_slug = slugify_value(name)
    slug = base_slug
    suffix = 2
    while db.scalar(select(Project).where(Project.slug == slug)) is not None:
        slug = f"{base_slug}-{suffix}"
        suffix += 1

    project = Project(
        organization_id=organization.id if organization else None,
        name=name.strip(),
        slug=slug,
        ownership_type=ownership_type.strip() or "company",
        summary=summary.strip() or None,
        primary_repo_path=primary_repo_path.strip() or None,
        status=status.strip() or "active",
    )
    db.add(project)
    db.commit()
    db.refresh(project)
    return project


def upsert_project_setting(db: Session, *, project: Project, key: str, value: str) -> ProjectSetting:
    setting = db.scalar(
        select(ProjectSetting).where(ProjectSetting.project_id == project.id, ProjectSetting.key == key.strip())
    )
    if setting is None:
        setting = ProjectSetting(project_id=project.id, key=key.strip(), value=value.strip())
        db.add(setting)
    else:
        setting.value = value.strip()
    db.commit()
    db.refresh(setting)
    return setting


def create_project_integration(
    db: Session,
    *,
    project: Project,
    integration_type: str,
    display_name: str,
    external_id: str,
    base_url: str,
    config_json: str,
    is_enabled: bool,
) -> ProjectIntegration:
    parsed_config: dict = {}
    if config_json.strip():
        parsed = json.loads(config_json)
        if isinstance(parsed, dict):
            parsed_config = parsed
        else:
            parsed_config = {"value": parsed}

    integration = ProjectIntegration(
        project_id=project.id,
        integration_type=integration_type.strip(),
        display_name=display_name.strip(),
        external_id=external_id.strip() or None,
        base_url=base_url.strip() or None,
        config_json=parsed_config,
        is_enabled=is_enabled,
    )
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


def delete_project_integration(db: Session, *, project: Project, integration_id: int) -> bool:
    integration = db.scalar(
        select(ProjectIntegration).where(
            ProjectIntegration.id == integration_id,
            ProjectIntegration.project_id == project.id,
        )
    )
    if integration is None:
        return False
    db.delete(integration)
    db.commit()
    return True

def update_project_integration_config(
    db: Session,
    *,
    project: Project,
    integration_id: int,
    updates: dict | None = None,
    remove_keys: list[str] | None = None,
) -> ProjectIntegration | None:
    integration = db.scalar(
        select(ProjectIntegration).where(
            ProjectIntegration.id == integration_id,
            ProjectIntegration.project_id == project.id,
        )
    )
    if integration is None:
        return None

    config = integration.config_json or {}
    if updates:
        config.update(updates)
    if remove_keys:
        for key in remove_keys:
            config.pop(key, None)
    integration.config_json = config
    db.add(integration)
    db.commit()
    db.refresh(integration)
    return integration


def create_project_person(
    db: Session,
    *,
    project: Project,
    name: str,
    role_title: str,
    relationship_type: str,
    external_ref: str,
    notes: str,
) -> ProjectPerson:
    person = ProjectPerson(
        project_id=project.id,
        name=name.strip(),
        role_title=role_title.strip() or None,
        relationship_type=relationship_type.strip() or None,
        external_ref=external_ref.strip() or None,
        notes=notes.strip() or None,
    )
    db.add(person)
    db.commit()
    db.refresh(person)
    return person


def create_project_context_entry(
    db: Session,
    *,
    project: Project,
    title: str,
    section: str,
    content: str,
    source_type: str,
    source_ref: str,
) -> ProjectContextEntry:
    entry = ProjectContextEntry(
        project_id=project.id,
        title=title.strip(),
        section=section.strip() or "general",
        content=content.strip(),
        source_type=source_type.strip() or "manual",
        source_ref=source_ref.strip() or None,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def create_assistant_profile(
    db: Session,
    *,
    project: Project,
    display_name: str,
    mission: str,
    tone_profile: str,
    response_constraints: str,
    escalation_policy: str,
    default_language: str,
    execution_mode: str,
    is_default: bool,
) -> AssistantProfile:
    if is_default:
        for profile in db.scalars(select(AssistantProfile).where(AssistantProfile.project_id == project.id)):
            profile.is_default = False

    profile = AssistantProfile(
        project_id=project.id,
        display_name=display_name.strip(),
        mission=mission.strip() or None,
        tone_profile=tone_profile.strip() or None,
        response_constraints=response_constraints.strip() or None,
        escalation_policy=escalation_policy.strip() or None,
        default_language=default_language.strip() or "tr",
        execution_mode=execution_mode.strip() or "draft-first",
        is_default=is_default,
    )
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def create_communication_style_rule(
    db: Session,
    *,
    project: Project,
    person_id: int | None,
    channel_type: str,
    audience_name: str,
    audience_role: str,
    style_summary: str,
    do_guidance: str,
    dont_guidance: str,
    sample_reply: str,
    source_type: str,
    is_active: bool,
) -> CommunicationStyleRule:
    person = None
    if person_id is not None:
        person = db.scalar(
            select(ProjectPerson).where(ProjectPerson.id == person_id, ProjectPerson.project_id == project.id)
        )

    style_rule = CommunicationStyleRule(
        project_id=project.id,
        person_id=person.id if person else None,
        channel_type=channel_type.strip(),
        audience_name=audience_name.strip() or None,
        audience_role=audience_role.strip() or None,
        style_summary=style_summary.strip(),
        do_guidance=do_guidance.strip() or None,
        dont_guidance=dont_guidance.strip() or None,
        sample_reply=sample_reply.strip() or None,
        source_type=source_type.strip() or "manual",
        is_active=is_active,
    )
    db.add(style_rule)
    db.commit()
    db.refresh(style_rule)
    return style_rule


def build_project_assistant_brief(project: Project) -> ProjectAssistantBrief:
    org_label = project.organization.name if project.organization else "Bagimsiz workspace"
    headline = f"{project.name} icin cloud assistant brief | workspace: {org_label}"
    sections = [
        (
            "SaaS Workspace",
            [
                f"Plan: {(project.organization.plan_tier if project.organization else 'starter')}",
                f"Ownership: {project.ownership_type}",
                f"Status: {project.status}",
                f"Primary repo: {project.primary_repo_path or 'Henuz baglanmadi'}",
            ],
        ),
        (
            "Assistant Profiles",
            [
                " | ".join(
                    filter(
                        None,
                        [
                            profile.display_name,
                            profile.default_language,
                            profile.execution_mode,
                            "default" if profile.is_default else "secondary",
                        ],
                    )
                )
                for profile in project.assistant_profiles
            ],
        ),
        (
            "Integrations",
            [
                " | ".join(
                    filter(
                        None,
                        [
                            integration.integration_type,
                            integration.display_name,
                            integration.base_url,
                            "enabled" if integration.is_enabled else "disabled",
                        ],
                    )
                )
                for integration in project.integrations
            ],
        ),
        (
            "People Graph",
            [
                " | ".join(
                    filter(
                        None,
                        [
                            person.name,
                            person.role_title,
                            person.relationship_type,
                            person.external_ref,
                        ],
                    )
                )
                for person in project.people
            ],
        ),
        (
            "Communication Rules",
            [
                " | ".join(
                    filter(
                        None,
                        [
                            rule.channel_type,
                            rule.person.name if rule.person else None,
                            rule.audience_name,
                            rule.audience_role,
                            rule.style_summary,
                        ],
                    )
                )
                for rule in project.communication_style_rules
                if rule.is_active
            ],
        ),
        (
            "Knowledge Sources",
            [
                " | ".join(
                    filter(
                        None,
                        [
                            context.section,
                            context.title,
                            context.source_type,
                            context.source_ref,
                        ],
                    )
                )
                for context in project.context_entries
            ],
        ),
    ]
    return ProjectAssistantBrief(headline=headline, sections=sections)



