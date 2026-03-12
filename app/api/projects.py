from __future__ import annotations

from datetime import datetime, timedelta, timezone
from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import APIRouter, Depends, File, Form, Query, Request, UploadFile, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db.models import Organization, Project
from app.db.session import get_db
from app.logging import get_logger
from app.services.activity_store import append_activity
from app.services.context_ingest import (
    ContextUpload,
    import_contexts_from_folder,
    import_contexts_from_uploads,
    suggest_context_prefix,
)
from app.services.knowledge_jobs import create_sync_job, list_sync_jobs, run_sync_job
from app.services.oauth_integrations import (
    build_atlassian_authorize_url,
    build_github_authorize_url,
    build_google_authorize_url,
    exchange_atlassian_code,
    exchange_github_code,
    exchange_google_code,
    fetch_atlassian_resources,
)
from app.services.projects import (
    build_project_assistant_brief,
    create_assistant_profile,
    create_communication_style_rule,
    create_organization,
    create_project,
    create_project_context_entry,
    create_project_integration,
    delete_project_integration,
    update_project_integration_config,
    create_project_person,
    get_organization,
    get_project,
    list_organizations,
    list_projects,
    upsert_project_setting,
)

router = APIRouter(tags=["projects"])
logger = get_logger(__name__)
templates = Jinja2Templates(directory=str(Path(__file__).resolve().parents[1] / "ui" / "templates"))

JOB_TYPES = [
    ("github_scan", "Repo tara (GitHub)"),
    ("jira_analysis", "Jira analiz et"),
    ("teams_style", "Teams stilini cikar"),
    ("whatsapp_style", "WhatsApp stilini cikar"),
    ("gmail_style", "Gmail stilini cikar"),
]


@router.get("/projects", response_class=HTMLResponse, response_model=None)
def projects_page(request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_project_access(request, "/projects")
    if access_redirect is not None:
        return access_redirect

    projects = list_projects(db)
    organizations = list_organizations(db)
    return templates.TemplateResponse(
        request=request,
        name="projects.html",
        context={
            "projects": projects,
            "organizations": organizations,
            "notice": request.query_params.get("notice", ""),
            "errors": request.query_params.getlist("errors"),
            "is_authenticated": _is_authenticated(request),
        },
    )


@router.post("/organizations", response_model=None)
def create_organization_page(
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(""),
    owner_name: str = Form(""),
    billing_email: str = Form(""),
    plan_tier: str = Form("starter"),
    summary: str = Form(""),
    status_value: str = Form("active"),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, "/projects")
    if access_redirect is not None:
        return access_redirect

    if not name.strip():
        return RedirectResponse(url="/projects?errors=Workspace%20adi%20zorunludur.", status_code=status.HTTP_302_FOUND)

    organization = create_organization(
        db,
        name=name,
        owner_name=owner_name,
        billing_email=billing_email,
        plan_tier=plan_tier,
        summary=summary,
        status=status_value,
    )
    append_activity(
        "organization_created",
        "Organization created",
        {"organization_id": organization.id, "organization_name": organization.name},
    )
    return RedirectResponse(url="/projects?notice=Workspace%20olusturuldu.", status_code=status.HTTP_302_FOUND)


@router.post("/projects", response_model=None)
def create_project_page(
    request: Request,
    db: Session = Depends(get_db),
    organization_id: str = Form(""),
    organization_name: str = Form(""),
    organization_owner_name: str = Form(""),
    organization_billing_email: str = Form(""),
    organization_plan_tier: str = Form("starter"),
    name: str = Form(""),
    ownership_type: str = Form("company"),
    summary: str = Form(""),
    primary_repo_path: str = Form(""),
    status_value: str = Form("active"),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, "/projects")
    if access_redirect is not None:
        return access_redirect

    if not name.strip():
        return RedirectResponse(url="/projects?errors=Proje%20adi%20zorunludur.", status_code=status.HTTP_302_FOUND)

    organization = _resolve_organization(
        db,
        organization_id=organization_id,
        organization_name=organization_name,
        owner_name=organization_owner_name,
        billing_email=organization_billing_email,
        plan_tier=organization_plan_tier,
    )
    if isinstance(organization, RedirectResponse):
        return organization

    project = create_project(
        db,
        organization=organization,
        name=name,
        ownership_type=ownership_type,
        summary=summary,
        primary_repo_path=primary_repo_path,
        status=status_value,
    )
    append_activity(
        "project_created",
        "Project created",
        {"project_id": project.id, "project_name": project.name, "organization_id": organization.id if organization else None},
    )
    return RedirectResponse(url=f"/projects/{project.id}?notice=Proje%20olusturuldu.", status_code=status.HTTP_302_FOUND)


@router.get("/projects/{project_id}", response_class=HTMLResponse, response_model=None)
def project_detail_page(project_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = get_project(db, project_id)
    if project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="project_detail.html",
        context={
            "project": project,
            "assistant_brief": build_project_assistant_brief(project),
            "notice": request.query_params.get("notice", ""),
            "errors": request.query_params.getlist("errors"),
            "context_prefix": suggest_context_prefix(project),
            "microsoft_connected": get_settings().microsoft_delegated_connected,
            "is_authenticated": _is_authenticated(request),
        },
    )


@router.get("/projects/{project_id}/context", response_class=HTMLResponse, response_model=None)
def project_context_page(project_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}/context")
    if access_redirect is not None:
        return access_redirect

    project = get_project(db, project_id)
    if project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    return templates.TemplateResponse(
        request=request,
        name="project_context.html",
        context={
            "project": project,
            "context_prefix": suggest_context_prefix(project),
            "notice": request.query_params.get("notice", ""),
            "errors": request.query_params.getlist("errors"),
            "is_authenticated": _is_authenticated(request),
        },
    )


@router.get("/projects/{project_id}/jobs", response_class=HTMLResponse, response_model=None)
def project_jobs_page(project_id: int, request: Request, db: Session = Depends(get_db)) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}/jobs")
    if access_redirect is not None:
        return access_redirect

    project = get_project(db, project_id)
    if project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    jobs = list_sync_jobs(db, project=project)
    return templates.TemplateResponse(
        request=request,
        name="project_jobs.html",
        context={
            "project": project,
            "jobs": jobs,
            "job_types": JOB_TYPES,
            "notice": request.query_params.get("notice", ""),
            "errors": request.query_params.getlist("errors"),
            "is_authenticated": _is_authenticated(request),
        },
    )


@router.post("/projects/{project_id}/jobs", response_model=None)
def project_jobs_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    job_type: str = Form(""),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}/jobs")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not job_type.strip():
        return RedirectResponse(url=f"/projects/{project_id}/jobs?errors=Job%20tipi%20zorunludur.", status_code=status.HTTP_302_FOUND)

    requested_by = request.session.get("panel_username") if request.session else None
    job = create_sync_job(db, project=project, job_type=job_type, requested_by=requested_by)
    run_sync_job(db, job=job, project=project)
    append_activity("project_sync_job_queued", "Project sync job queued", {"project_id": project.id, "job_type": job_type})
    return RedirectResponse(url=f"/projects/{project_id}/jobs?notice=Job%20kuyruga%20alindi.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/settings", response_model=None)
def project_setting_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    key: str = Form(""),
    value: str = Form(""),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not key.strip():
        return RedirectResponse(url=f"/projects/{project_id}?errors=Ayar%20anahtari%20zorunludur.", status_code=status.HTTP_302_FOUND)
    upsert_project_setting(db, project=project, key=key, value=value)
    append_activity("project_setting_saved", "Project setting saved", {"project_id": project.id, "key": key})
    return RedirectResponse(url=f"/projects/{project_id}?notice=Ayar%20kaydedildi.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/integrations", response_model=None)
def project_integration_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    integration_type: str = Form(""),
    display_name: str = Form(""),
    external_id: str = Form(""),
    base_url: str = Form(""),
    config_json: str = Form(""),
    is_enabled: str = Form("true"),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not integration_type.strip() or not display_name.strip():
        return RedirectResponse(url=f"/projects/{project_id}?errors=Entegrasyon%20tipi%20ve%20adi%20zorunludur.", status_code=status.HTTP_302_FOUND)
    try:
        create_project_integration(
            db,
            project=project,
            integration_type=integration_type,
            display_name=display_name,
            external_id=external_id,
            base_url=base_url,
            config_json=config_json,
            is_enabled=is_enabled.lower() != "false",
        )
    except Exception as exc:
        logger.warning("project_integration_create_failed", extra={"project_id": project_id, "error": str(exc)})
        return RedirectResponse(url=f"/projects/{project_id}?errors=Entegrasyon%20kaydedilemedi.", status_code=status.HTTP_302_FOUND)
    append_activity(
        "project_integration_saved",
        "Project integration saved",
        {"project_id": project.id, "integration_type": integration_type},
    )
    return RedirectResponse(url=f"/projects/{project_id}?notice=Entegrasyon%20kaydedildi.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/integrations/{integration_id}/delete", response_model=None)
def project_integration_delete(
    project_id: int,
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project

    deleted = delete_project_integration(db, project=project, integration_id=integration_id)
    if not deleted:
        return RedirectResponse(
            url=f"/projects/{project_id}?errors=Entegrasyon%20bulunamadi.",
            status_code=status.HTTP_302_FOUND,
        )

    append_activity(
        "project_integration_deleted",
        "Project integration deleted",
        {"project_id": project.id, "integration_id": integration_id},
    )
    return RedirectResponse(url=f"/projects/{project_id}?notice=Entegrasyon%20silindi.", status_code=status.HTTP_302_FOUND)

@router.get("/projects/{project_id}/integrations/connect/{integration_type}", response_model=None)
def project_integration_quick_connect(
    project_id: int,
    integration_type: str,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project

    normalized_type = integration_type.strip().lower()
    if normalized_type not in ("github", "gmail", "jira"):
        return RedirectResponse(
            url=f"/projects/{project_id}?errors=Desteklenmeyen%20entegrasyon%20tipi.",
            status_code=status.HTTP_302_FOUND,
        )

    integration = next(
        (item for item in project.integrations if item.integration_type == normalized_type),
        None,
    )

    if integration is None:
        display_map = {
            "github": "GitHub",
            "gmail": "Gmail",
            "jira": "Jira",
        }
        base_url_map = {
            "github": "https://api.github.com",
            "gmail": "",
            "jira": "",
        }
        integration = create_project_integration(
            db,
            project=project,
            integration_type=normalized_type,
            display_name=display_map[normalized_type],
            external_id="",
            base_url=base_url_map[normalized_type],
            config_json="{}",
            is_enabled=True,
        )
        append_activity(
            "project_integration_saved",
            "Project integration saved",
            {"project_id": project.id, "integration_type": normalized_type},
        )
    else:
        if not integration.is_enabled:
            integration.is_enabled = True
            db.commit()

    cfg = integration.config_json or {}
    if normalized_type == "github":
        connected = cfg.get("access_token") or cfg.get("token")
    else:
        connected = cfg.get("refresh_token") or cfg.get("access_token")

    if connected:
        return RedirectResponse(
            url=f"/projects/{project_id}?notice=Entegrasyon%20zaten%20bagli.",
            status_code=status.HTTP_302_FOUND,
        )

    return RedirectResponse(
        url=f"/projects/{project_id}/integrations/{integration.id}/connect",
        status_code=status.HTTP_302_FOUND,
    )

@router.get("/projects/{project_id}/integrations/{integration_id}/connect", response_model=None)
def project_integration_connect(
    project_id: int,
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project

    integration = _find_project_integration(project, integration_id)
    if integration is None:
        return RedirectResponse(url=f"/projects/{project_id}?errors=Entegrasyon%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    settings = get_settings()
    if not settings.public_webhook_base_url:
        return RedirectResponse(url=f"/projects/{project_id}?errors=PUBLIC_WEBHOOK_BASE_URL%20eksik.", status_code=status.HTTP_302_FOUND)

    state = token_urlsafe(24)
    if integration.integration_type == "github":
        if not settings.github_client_id or not settings.github_client_secret:
            return RedirectResponse(url=f"/projects/{project_id}?errors=GitHub%20client%20ayarlari%20eksik.", status_code=status.HTTP_302_FOUND)
        redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/github/callback"
        _store_oauth_state(request, "github", state, project_id, integration_id)
        url = build_github_authorize_url(
            client_id=settings.github_client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope="repo",
        )
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

    if integration.integration_type == "gmail":
        if not settings.google_client_id or not settings.google_client_secret:
            return RedirectResponse(url=f"/projects/{project_id}?errors=Google%20client%20ayarlari%20eksik.", status_code=status.HTTP_302_FOUND)
        redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/google/callback"
        _store_oauth_state(request, "google", state, project_id, integration_id)
        url = build_google_authorize_url(
            client_id=settings.google_client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope="https://www.googleapis.com/auth/gmail.readonly",
        )
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

    if integration.integration_type == "jira":
        if not settings.atlassian_client_id or not settings.atlassian_client_secret:
            return RedirectResponse(url=f"/projects/{project_id}?errors=Atlassian%20client%20ayarlari%20eksik.", status_code=status.HTTP_302_FOUND)
        redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/atlassian/callback"
        _store_oauth_state(request, "atlassian", state, project_id, integration_id)
        url = build_atlassian_authorize_url(
            client_id=settings.atlassian_client_id,
            redirect_uri=redirect_uri,
            state=state,
            scope="read:jira-work read:jira-user offline_access",
        )
        return RedirectResponse(url=url, status_code=status.HTTP_302_FOUND)

    return RedirectResponse(url=f"/projects/{project_id}?errors=Bu%20entegrasyon%20icin%20OAuth%20destegi%20yok.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/integrations/{integration_id}/disconnect", response_model=None)
def project_integration_disconnect(
    project_id: int,
    integration_id: int,
    request: Request,
    db: Session = Depends(get_db),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project

    integration = _find_project_integration(project, integration_id)
    if integration is None:
        return RedirectResponse(url=f"/projects/{project_id}?errors=Entegrasyon%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    remove_keys = [
        "access_token",
        "refresh_token",
        "expires_at",
        "scope",
        "token_type",
        "cloud_id",
        "resource_url",
        "resource_name",
    ]
    if integration.integration_type == "github":
        remove_keys.append("token")

    updated = update_project_integration_config(
        db,
        project=project,
        integration_id=integration_id,
        updates=None,
        remove_keys=remove_keys,
    )
    if updated is None:
        return RedirectResponse(url=f"/projects/{project_id}?errors=Entegrasyon%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    append_activity(
        "project_integration_disconnected",
        "Project integration disconnected",
        {"project_id": project.id, "integration_id": integration_id},
    )
    return RedirectResponse(url=f"/projects/{project_id}?notice=Entegrasyon%20baglantisi%20kaldirildi.", status_code=status.HTTP_302_FOUND)


@router.get("/auth/github/callback", response_model=None)
def github_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    project_id, integration_id, stored_state = _consume_oauth_state(request, "github")
    if error:
        return _oauth_error_redirect(project_id, error_description or error)
    if not code or not state or state != stored_state:
        return _oauth_error_redirect(project_id, "GitHub login dogrulamasi basarisiz.")
    if integration_id is None:
        return _oauth_error_redirect(project_id, "OAuth kaydi bulunamadi.")

    settings = get_settings()
    if not settings.public_webhook_base_url:
        return _oauth_error_redirect(project_id, "PUBLIC_WEBHOOK_BASE_URL eksik.")
    if not settings.github_client_id or not settings.github_client_secret:
        return _oauth_error_redirect(project_id, "GitHub client ayarlari eksik.")

    redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/github/callback"
    result = exchange_github_code(
        client_id=settings.github_client_id,
        client_secret=settings.github_client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )
    if not result.success or not result.access_token:
        return _oauth_error_redirect(project_id, result.error or "GitHub token alinamadi.")

    project = _load_project_or_redirect(db, project_id) if project_id else None
    if isinstance(project, RedirectResponse) or project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    update_project_integration_config(
        db,
        project=project,
        integration_id=integration_id,
        updates={
            "access_token": result.access_token,
            "token_type": result.token_type,
            "scope": result.scope,
        },
        remove_keys=None,
    )
    append_activity("github_connected", "GitHub connected", {"project_id": project.id, "integration_id": integration_id})
    return RedirectResponse(url=f"/projects/{project.id}?notice=GitHub%20baglandi.", status_code=status.HTTP_302_FOUND)


@router.get("/auth/google/callback", response_model=None)
def google_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    project_id, integration_id, stored_state = _consume_oauth_state(request, "google")
    if error:
        return _oauth_error_redirect(project_id, error_description or error)
    if not code or not state or state != stored_state:
        return _oauth_error_redirect(project_id, "Google login dogrulamasi basarisiz.")
    if integration_id is None:
        return _oauth_error_redirect(project_id, "OAuth kaydi bulunamadi.")

    settings = get_settings()
    if not settings.public_webhook_base_url:
        return _oauth_error_redirect(project_id, "PUBLIC_WEBHOOK_BASE_URL eksik.")
    if not settings.google_client_id or not settings.google_client_secret:
        return _oauth_error_redirect(project_id, "Google client ayarlari eksik.")

    redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/google/callback"
    result = exchange_google_code(
        client_id=settings.google_client_id,
        client_secret=settings.google_client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )
    if not result.success or not result.access_token:
        return _oauth_error_redirect(project_id, result.error or "Google token alinamadi.")

    project = _load_project_or_redirect(db, project_id) if project_id else None
    if isinstance(project, RedirectResponse) or project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    updates = {
        "access_token": result.access_token,
        "token_type": result.token_type,
        "scope": result.scope,
    }
    if result.refresh_token:
        updates["refresh_token"] = result.refresh_token
    if result.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.expires_in)
        updates["expires_at"] = expires_at.isoformat()

    update_project_integration_config(
        db,
        project=project,
        integration_id=integration_id,
        updates=updates,
        remove_keys=None,
    )
    append_activity("google_connected", "Google connected", {"project_id": project.id, "integration_id": integration_id})
    return RedirectResponse(url=f"/projects/{project.id}?notice=Google%20baglandi.", status_code=status.HTTP_302_FOUND)


@router.get("/auth/atlassian/callback", response_model=None)
def atlassian_oauth_callback(
    request: Request,
    db: Session = Depends(get_db),
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    project_id, integration_id, stored_state = _consume_oauth_state(request, "atlassian")
    if error:
        return _oauth_error_redirect(project_id, error_description or error)
    if not code or not state or state != stored_state:
        return _oauth_error_redirect(project_id, "Atlassian login dogrulamasi basarisiz.")
    if integration_id is None:
        return _oauth_error_redirect(project_id, "OAuth kaydi bulunamadi.")

    settings = get_settings()
    if not settings.public_webhook_base_url:
        return _oauth_error_redirect(project_id, "PUBLIC_WEBHOOK_BASE_URL eksik.")
    if not settings.atlassian_client_id or not settings.atlassian_client_secret:
        return _oauth_error_redirect(project_id, "Atlassian client ayarlari eksik.")

    redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/atlassian/callback"
    result = exchange_atlassian_code(
        client_id=settings.atlassian_client_id,
        client_secret=settings.atlassian_client_secret,
        code=code,
        redirect_uri=redirect_uri,
    )
    if not result.success or not result.access_token:
        return _oauth_error_redirect(project_id, result.error or "Atlassian token alinamadi.")

    project = _load_project_or_redirect(db, project_id) if project_id else None
    if isinstance(project, RedirectResponse) or project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    updates = {
        "access_token": result.access_token,
        "token_type": result.token_type,
        "scope": result.scope,
    }
    if result.refresh_token:
        updates["refresh_token"] = result.refresh_token
    if result.expires_in:
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=result.expires_in)
        updates["expires_at"] = expires_at.isoformat()

    resources = fetch_atlassian_resources(access_token=result.access_token)
    if resources:
        resource = resources[0]
        updates["cloud_id"] = resource.get("id")
        updates["resource_url"] = resource.get("url")
        updates["resource_name"] = resource.get("name")

    update_project_integration_config(
        db,
        project=project,
        integration_id=integration_id,
        updates=updates,
        remove_keys=None,
    )
    append_activity("atlassian_connected", "Atlassian connected", {"project_id": project.id, "integration_id": integration_id})
    return RedirectResponse(url=f"/projects/{project.id}?notice=Atlassian%20baglandi.", status_code=status.HTTP_302_FOUND)

@router.post("/projects/{project_id}/people", response_model=None)
def project_person_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    name: str = Form(""),
    role_title: str = Form(""),
    relationship_type: str = Form(""),
    external_ref: str = Form(""),
    notes: str = Form(""),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not name.strip():
        return RedirectResponse(url=f"/projects/{project_id}?errors=Kisi%20adi%20zorunludur.", status_code=status.HTTP_302_FOUND)
    create_project_person(
        db,
        project=project,
        name=name,
        role_title=role_title,
        relationship_type=relationship_type,
        external_ref=external_ref,
        notes=notes,
    )
    append_activity("project_person_saved", "Project person saved", {"project_id": project.id, "person_name": name})
    return RedirectResponse(url=f"/projects/{project_id}?notice=Kisi%20kaydedildi.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/contexts", response_model=None)
def project_context_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    title: str = Form(""),
    section: str = Form("general"),
    content: str = Form(""),
    source_type: str = Form("manual"),
    source_ref: str = Form(""),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not title.strip() or not content.strip():
        return RedirectResponse(url=f"/projects/{project_id}/context?errors=Context%20basligi%20ve%20icerigi%20zorunludur.", status_code=status.HTTP_302_FOUND)
    create_project_context_entry(
        db,
        project=project,
        title=title,
        section=section,
        content=content,
        source_type=source_type,
        source_ref=source_ref,
    )
    append_activity("project_context_saved", "Project context saved", {"project_id": project.id, "title": title})
    return RedirectResponse(url=f"/projects/{project_id}/context?notice=Context%20kaydedildi.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/contexts/import-folder", response_model=None)
def project_context_import_from_folder(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    prefix: str = Form(""),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project

    contexts_dir = Path(__file__).resolve().parents[2] / "contexts"
    if not contexts_dir.exists():
        return RedirectResponse(url=f"/projects/{project_id}/context?errors=contexts%20klasoru%20bulunamadi.", status_code=status.HTTP_302_FOUND)

    result = import_contexts_from_folder(
        db,
        project=project,
        contexts_dir=contexts_dir,
        prefix_override=prefix.strip() or None,
    )

    notice = _build_context_notice(result)
    query = f"notice={quote(notice)}" if notice else ""
    if result.errors:
        query = _append_query_error(query, "; ".join(result.errors))
    return RedirectResponse(url=f"/projects/{project_id}/context?{query}", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/contexts/upload", response_model=None)
async def project_context_upload(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    files: list[UploadFile] = File([]),
    section: str = Form("general"),
    source_type: str = Form("upload"),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not files:
        return RedirectResponse(url=f"/projects/{project_id}/context?errors=Yuklenecek%20dosya%20sec.", status_code=status.HTTP_302_FOUND)

    uploads: list[ContextUpload] = []
    for upload in files:
        payload = await upload.read()
        if payload:
            uploads.append(ContextUpload(filename=upload.filename or "upload.txt", payload=payload, content_type=upload.content_type))

    if not uploads:
        return RedirectResponse(url=f"/projects/{project_id}/context?errors=Dosya%20icerigi%20bos.", status_code=status.HTTP_302_FOUND)

    result = import_contexts_from_uploads(
        db,
        project=project,
        uploads=uploads,
        section=section,
        source_type=source_type,
    )

    notice = _build_context_notice(result)
    query = f"notice={quote(notice)}" if notice else ""
    if result.errors:
        query = _append_query_error(query, "; ".join(result.errors))
    return RedirectResponse(url=f"/projects/{project_id}/context?{query}", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/assistant-profiles", response_model=None)
def assistant_profile_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    display_name: str = Form(""),
    mission: str = Form(""),
    tone_profile: str = Form(""),
    response_constraints: str = Form(""),
    escalation_policy: str = Form(""),
    default_language: str = Form("tr"),
    execution_mode: str = Form("draft-first"),
    is_default: str = Form("true"),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not display_name.strip():
        return RedirectResponse(url=f"/projects/{project_id}?errors=Assistant%20adi%20zorunludur.", status_code=status.HTTP_302_FOUND)

    create_assistant_profile(
        db,
        project=project,
        display_name=display_name,
        mission=mission,
        tone_profile=tone_profile,
        response_constraints=response_constraints,
        escalation_policy=escalation_policy,
        default_language=default_language,
        execution_mode=execution_mode,
        is_default=is_default.lower() != "false",
    )
    append_activity(
        "assistant_profile_saved",
        "Assistant profile saved",
        {"project_id": project.id, "display_name": display_name},
    )
    return RedirectResponse(url=f"/projects/{project_id}?notice=Assistant%20profili%20kaydedildi.", status_code=status.HTTP_302_FOUND)


@router.post("/projects/{project_id}/style-rules", response_model=None)
def communication_style_rule_create(
    project_id: int,
    request: Request,
    db: Session = Depends(get_db),
    person_id: str = Form(""),
    channel_type: str = Form(""),
    audience_name: str = Form(""),
    audience_role: str = Form(""),
    style_summary: str = Form(""),
    do_guidance: str = Form(""),
    dont_guidance: str = Form(""),
    sample_reply: str = Form(""),
    source_type: str = Form("manual"),
    is_active: str = Form("true"),
) -> RedirectResponse:
    access_redirect = _guard_project_access(request, f"/projects/{project_id}")
    if access_redirect is not None:
        return access_redirect

    project = _load_project_or_redirect(db, project_id)
    if isinstance(project, RedirectResponse):
        return project
    if not channel_type.strip() or not style_summary.strip():
        return RedirectResponse(url=f"/projects/{project_id}?errors=Kanal%20ve%20stil%20ozeti%20zorunludur.", status_code=status.HTTP_302_FOUND)

    parsed_person_id = _parse_int(person_id)
    create_communication_style_rule(
        db,
        project=project,
        person_id=parsed_person_id,
        channel_type=channel_type,
        audience_name=audience_name,
        audience_role=audience_role,
        style_summary=style_summary,
        do_guidance=do_guidance,
        dont_guidance=dont_guidance,
        sample_reply=sample_reply,
        source_type=source_type,
        is_active=is_active.lower() != "false",
    )
    append_activity(
        "communication_style_rule_saved",
        "Communication style rule saved",
        {"project_id": project.id, "channel_type": channel_type},
    )
    return RedirectResponse(url=f"/projects/{project_id}?notice=Iletisim%20stili%20kaydedildi.", status_code=status.HTTP_302_FOUND)


def _find_project_integration(project: Project, integration_id: int):
    for integration in project.integrations:
        if integration.id == integration_id:
            return integration
    return None


def _store_oauth_state(request: Request, provider: str, state: str, project_id: int, integration_id: int) -> None:
    request.session[f"{provider}_oauth_state"] = state
    request.session[f"{provider}_oauth_project_id"] = str(project_id)
    request.session[f"{provider}_oauth_integration_id"] = str(integration_id)


def _consume_oauth_state(request: Request, provider: str) -> tuple[int | None, int | None, str | None]:
    state_key = f"{provider}_oauth_state"
    project_key = f"{provider}_oauth_project_id"
    integration_key = f"{provider}_oauth_integration_id"

    stored_state = request.session.get(state_key)
    project_id_raw = request.session.get(project_key)
    integration_id_raw = request.session.get(integration_key)

    request.session.pop(state_key, None)
    request.session.pop(project_key, None)
    request.session.pop(integration_key, None)

    project_id = _parse_int(str(project_id_raw)) if project_id_raw is not None else None
    integration_id = _parse_int(str(integration_id_raw)) if integration_id_raw is not None else None
    return project_id, integration_id, stored_state


def _oauth_error_redirect(project_id: int | None, message: str) -> RedirectResponse:
    if project_id:
        return RedirectResponse(url=f"/projects/{project_id}?errors={quote(message)}", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url=f"/projects?errors={quote(message)}", status_code=status.HTTP_302_FOUND)

def _build_context_notice(result) -> str:
    parts: list[str] = []
    if result.imported:
        parts.append(f"{result.imported} yeni context")
    if result.updated:
        parts.append(f"{result.updated} guncellendi")
    if result.skipped:
        parts.append(f"{result.skipped} atlandi")
    return ", ".join(parts) + "." if parts else "Context bulunamadi."


def _append_query_error(query: str, error: str) -> str:
    if query:
        return f"{query}&errors={quote(error)}"
    return f"errors={quote(error)}"


def _resolve_organization(
    db: Session,
    *,
    organization_id: str,
    organization_name: str,
    owner_name: str,
    billing_email: str,
    plan_tier: str,
) -> Organization | None | RedirectResponse:
    parsed_id = _parse_int(organization_id)
    if parsed_id is not None:
        organization = get_organization(db, parsed_id)
        if organization is None:
            return RedirectResponse(url="/projects?errors=Secilen%20workspace%20bulunamadi.", status_code=status.HTTP_302_FOUND)
        return organization

    if organization_name.strip():
        return create_organization(
            db,
            name=organization_name,
            owner_name=owner_name,
            billing_email=billing_email,
            plan_tier=plan_tier,
        )

    organizations = list_organizations(db)
    if len(organizations) == 1:
        return organizations[0]
    if not organizations:
        return RedirectResponse(url="/projects?errors=Once%20bir%20workspace%20olustur%20veya%20projeyle%20birlikte%20tanimla.", status_code=status.HTTP_302_FOUND)
    return RedirectResponse(url="/projects?errors=Birden%20fazla%20workspace%20var.%20Lutfen%20birini%20sec.", status_code=status.HTTP_302_FOUND)


def _parse_int(value: str) -> int | None:
    stripped = value.strip()
    if not stripped:
        return None
    try:
        return int(stripped)
    except ValueError:
        return None


def _load_project_or_redirect(db: Session, project_id: int) -> Project | RedirectResponse:
    project = get_project(db, project_id)
    if project is None:
        return RedirectResponse(url="/projects?errors=Proje%20bulunamadi.", status_code=status.HTTP_302_FOUND)
    return project


def _guard_project_access(request: Request, next_url: str) -> RedirectResponse | None:
    settings = get_settings()
    if settings.panel_auth_configured and not _is_authenticated(request):
        return RedirectResponse(url=f"/login?next={next_url}", status_code=status.HTTP_302_FOUND)
    return None


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("panel_authenticated"))
























