from __future__ import annotations

from pathlib import Path
from secrets import token_urlsafe
from urllib.parse import quote

from fastapi import APIRouter, Form, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.adapters.graph_client import GraphClient
from app.adapters.telegram_client import TelegramClient
from app.config import get_settings
from app.db.models import TeamsMessage, TriageResult
from app.db.session import get_session_factory, reset_db_state
from app.logging import configure_logging, get_recent_logs, get_logger
from app.services.activity_store import append_activity
from app.services.app_settings import read_chat_labels
from app.services.graph_subscriptions import build_manual_chat_target, load_teams_settings_data, save_subscription_labels, subscribe_to_targets
from app.services.setup_manager import (
    get_general_config_summary,
    get_general_form_defaults,
    get_teams_form_defaults,
    is_setup_complete,
    save_general_settings,
    save_teams_settings,
    test_database_connection,
)
from app.services.telegram_polling import refresh_telegram_polling_state
from app.services.triage import triage_message

router = APIRouter(tags=["control-panel"])
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "ui" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = get_logger(__name__)


@router.get("/", response_class=HTMLResponse, response_model=None)
def root(request: Request) -> RedirectResponse:
    if not _is_authenticated(request) and get_settings().panel_auth_configured:
        return _redirect_to_login("/console")
    return RedirectResponse(url="/console" if is_setup_complete() else "/settings/general", status_code=status.HTTP_302_FOUND)


@router.get("/login", response_class=HTMLResponse, response_model=None)
def login_page(request: Request, error: str | None = None) -> HTMLResponse:
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="login.html",
        context={
            "error": error,
            "auth_configured": settings.panel_auth_configured,
            "is_authenticated": _is_authenticated(request),
        },
    )


@router.post("/login", response_class=HTMLResponse, response_model=None)
def login_submit(
    request: Request,
    username: str = Form(""),
    password: str = Form(""),
    next_url: str = Form("/console"),
) -> HTMLResponse | RedirectResponse:
    settings = get_settings()
    if not settings.panel_auth_configured:
        return RedirectResponse(url="/settings/general", status_code=status.HTTP_302_FOUND)

    if username != settings.panel_login_username or password != settings.panel_login_password:
        return templates.TemplateResponse(
            request=request,
            name="login.html",
            context={
                "error": "Kullanici adi veya sifre hatali.",
                "auth_configured": True,
                "is_authenticated": False,
            },
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    request.session["panel_authenticated"] = True
    request.session["panel_username"] = username
    append_activity("panel_login", "Panel login successful", {"username": username})
    return RedirectResponse(url=_sanitize_next_url(next_url), status_code=status.HTTP_302_FOUND)


@router.get("/logout", response_model=None)
def logout(request: Request) -> RedirectResponse:
    request.session.clear()
    return RedirectResponse(url="/login", status_code=status.HTTP_302_FOUND)


@router.get("/setup", response_model=None)
def setup_redirect() -> RedirectResponse:
    return RedirectResponse(url="/settings/general", status_code=status.HTTP_302_FOUND)


@router.get("/console", response_class=HTMLResponse, response_model=None)
def console_page(request: Request) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_panel_access(request, "/console")
    if access_redirect is not None:
        return access_redirect
    if not is_setup_complete():
        return RedirectResponse(url="/settings/general", status_code=status.HTTP_302_FOUND)
    return _render_dashboard(request=request)


@router.get("/settings/general", response_class=HTMLResponse, response_model=None)
def general_settings_page(request: Request, notice: str | None = None, db_message: str | None = None, errors: list[str] | None = None) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/general")
    if access_redirect is not None:
        return access_redirect
    return _render_general_settings(request=request, notice=notice, db_message=db_message, errors=errors or [])


@router.post("/settings/general", response_class=HTMLResponse, response_model=None)
async def save_general_settings_page(
    request: Request,
    database_url: str = Form(""),
    app_name: str = Form("ProjectAssistant"),
    app_env: str = Form("local"),
    log_level: str = Form("INFO"),
    preferred_language: str = Form("tr"),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    telegram_approval_mode: str = Form("polling"),
    telegram_poll_interval_seconds: str = Form("5"),
    public_webhook_base_url: str = Form(""),
    openai_api_key: str = Form(""),
    panel_login_username: str = Form("sinan"),
    panel_login_password: str = Form(""),
    panel_session_secret: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/general")
    if access_redirect is not None:
        return access_redirect

    values = {
        "DATABASE_URL": database_url,
        "APP_NAME": app_name,
        "APP_ENV": app_env,
        "LOG_LEVEL": log_level,
        "PREFERRED_LANGUAGE": preferred_language,
        "TELEGRAM_BOT_TOKEN": telegram_bot_token,
        "TELEGRAM_CHAT_ID": telegram_chat_id,
        "TELEGRAM_APPROVAL_MODE": telegram_approval_mode,
        "TELEGRAM_POLL_INTERVAL_SECONDS": telegram_poll_interval_seconds,
        "PUBLIC_WEBHOOK_BASE_URL": public_webhook_base_url,
        "OPENAI_API_KEY": openai_api_key,
        "PANEL_LOGIN_USERNAME": panel_login_username,
        "PANEL_LOGIN_PASSWORD": panel_login_password,
        "PANEL_SESSION_SECRET": panel_session_secret,
    }

    ok, db_message = test_database_connection(database_url)
    if ok:
        save_general_settings(values)
        from app.config import get_settings as get_cached_settings

        get_cached_settings.cache_clear()
        reset_db_state()
        configure_logging()
        await refresh_telegram_polling_state()
        append_activity("general_settings_saved", "General settings saved", {"database_ok": ok})
        return _render_general_settings(request=request, notice="Genel ayarlar kaydedildi.", db_message=db_message, errors=[])

    return _render_general_settings(request=request, notice="", db_message=db_message, errors=["Veritabani baglantisi kurulamadigi icin ayarlar kaydedilmedi."])


@router.post("/settings/general/telegram-webhook/activate", response_class=HTMLResponse, response_model=None)
async def activate_telegram_webhook(request: Request) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/general")
    if access_redirect is not None:
        return access_redirect

    settings = get_settings()
    errors: list[str] = []
    notice = ""
    if not settings.telegram_bot_token:
        errors.append("Telegram bot token eksik.")
    elif not settings.public_webhook_base_url:
        errors.append("PUBLIC_WEBHOOK_BASE_URL ayari eksik.")
    else:
        webhook_url = settings.public_webhook_base_url.rstrip("/") + "/webhooks/telegram"
        client = TelegramClient(bot_token=settings.telegram_bot_token)
        if client.set_webhook(webhook_url=webhook_url):
            notice = "Telegram webhook aktif edildi. Approval mode degerini webhook olarak kullanman tavsiye edilir."
        else:
            errors.append("Telegram webhook aktif edilemedi.")

    await refresh_telegram_polling_state()
    return _render_general_settings(request=request, notice=notice, db_message=None, errors=errors)


@router.post("/settings/general/telegram-webhook/deactivate", response_class=HTMLResponse, response_model=None)
async def deactivate_telegram_webhook(request: Request) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/general")
    if access_redirect is not None:
        return access_redirect

    settings = get_settings()
    errors: list[str] = []
    notice = ""
    if not settings.telegram_bot_token:
        errors.append("Telegram bot token eksik.")
    else:
        client = TelegramClient(bot_token=settings.telegram_bot_token)
        if client.delete_webhook():
            notice = "Telegram webhook kapatildi. Polling kullanacaksan artik conflict gormemelisin."
        else:
            errors.append("Telegram webhook kapatilamadi.")

    await refresh_telegram_polling_state()
    return _render_general_settings(request=request, notice=notice, db_message=None, errors=errors)


@router.get("/settings/teams", response_class=HTMLResponse, response_model=None)
def teams_settings_page(request: Request, notice: str | None = None, errors: list[str] | None = None) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect
    return _render_teams_settings(request=request, notice=notice or "", errors=errors or [], fetch_targets=False)


@router.post("/settings/teams", response_class=HTMLResponse, response_model=None)
async def save_teams_settings_page(
    request: Request,
    target_name: str = Form("Sinan"),
    watched_channels: str = Form(""),
    relevance_keywords: str = Form(""),
    microsoft_tenant_id: str = Form(""),
    microsoft_client_id: str = Form(""),
    microsoft_client_secret: str = Form(""),
    microsoft_user_id: str = Form(""),
    microsoft_graph_base_url: str = Form("https://graph.microsoft.com/v1.0"),
    graph_webhook_client_state: str = Form(""),
    graph_subscription_resource: str = Form(""),
    graph_notification_include_resource_data: str = Form("false"),
    teams_webhook_secret: str = Form(""),
    teams_bot_token: str = Form(""),
    teams_reply_url: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect

    values = {
        "TARGET_NAME": target_name,
        "WATCHED_CHANNELS": watched_channels,
        "RELEVANCE_KEYWORDS": relevance_keywords,
        "MICROSOFT_TENANT_ID": microsoft_tenant_id,
        "MICROSOFT_CLIENT_ID": microsoft_client_id,
        "MICROSOFT_CLIENT_SECRET": microsoft_client_secret,
        "MICROSOFT_USER_ID": microsoft_user_id,
        "MICROSOFT_GRAPH_BASE_URL": microsoft_graph_base_url,
        "GRAPH_WEBHOOK_CLIENT_STATE": graph_webhook_client_state,
        "GRAPH_SUBSCRIPTION_RESOURCE": graph_subscription_resource,
        "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA": graph_notification_include_resource_data,
        "TEAMS_WEBHOOK_SECRET": teams_webhook_secret,
        "TEAMS_BOT_TOKEN": teams_bot_token,
        "TEAMS_REPLY_URL": teams_reply_url,
    }
    save_teams_settings(values)

    from app.config import get_settings as get_cached_settings

    get_cached_settings.cache_clear()
    reset_db_state()
    configure_logging()
    await refresh_telegram_polling_state()
    append_activity("teams_settings_saved", "Teams settings saved", {})
    return _render_teams_settings(request=request, notice="Teams ayarlari kaydedildi.", errors=[], fetch_targets=False)


@router.get("/auth/microsoft/start", response_model=None)
def start_microsoft_auth(request: Request) -> RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect

    settings = get_settings()
    if not settings.public_webhook_base_url:
        return RedirectResponse(url="/settings/teams?errors=PUBLIC_WEBHOOK_BASE_URL%20eksik.", status_code=status.HTTP_302_FOUND)

    client = GraphClient.from_settings()
    redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/microsoft/callback"
    state = token_urlsafe(24)
    authorization_url = client.build_delegated_authorization_url(redirect_uri=redirect_uri, state=state)
    if authorization_url is None:
        return RedirectResponse(url="/settings/teams?errors=Microsoft%20Graph%20kimlik%20bilgileri%20eksik.", status_code=status.HTTP_302_FOUND)

    request.session["microsoft_oauth_state"] = state
    return RedirectResponse(url=authorization_url, status_code=status.HTTP_302_FOUND)


@router.get("/auth/microsoft/callback", response_model=None)
def microsoft_auth_callback(
    request: Request,
    code: str | None = Query(default=None),
    state: str | None = Query(default=None),
    error: str | None = Query(default=None),
    error_description: str | None = Query(default=None),
) -> RedirectResponse:
    stored_state = request.session.get("microsoft_oauth_state")
    request.session.pop("microsoft_oauth_state", None)

    if error:
        return RedirectResponse(url=f"/settings/teams?errors={quote(error_description or error)}", status_code=status.HTTP_302_FOUND)
    if not code or not state or state != stored_state:
        return RedirectResponse(url="/settings/teams?errors=Microsoft%20login%20dogrulamasi%20basarisiz.", status_code=status.HTTP_302_FOUND)

    settings = get_settings()
    if not settings.public_webhook_base_url:
        return RedirectResponse(url="/settings/teams?errors=PUBLIC_WEBHOOK_BASE_URL%20eksik.", status_code=status.HTTP_302_FOUND)

    client = GraphClient.from_settings()
    redirect_uri = settings.public_webhook_base_url.rstrip("/") + "/auth/microsoft/callback"
    result = client.exchange_delegated_code(code=code, redirect_uri=redirect_uri)
    if not result.success:
        return RedirectResponse(url=f"/settings/teams?errors={quote(result.error or 'Microsoft%20login%20basarisiz.')}", status_code=status.HTTP_302_FOUND)

    append_activity("microsoft_account_connected", "Microsoft delegated account connected", {"user": result.connected_user or "unknown"})
    return RedirectResponse(url=f"/settings/teams?notice={quote('Microsoft hesabi baglandi.')}", status_code=status.HTTP_302_FOUND)


@router.post("/auth/microsoft/disconnect", response_model=None)
def disconnect_microsoft_auth(request: Request) -> RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect

    client = GraphClient.from_settings()
    client.disconnect_delegated_identity()
    append_activity("microsoft_account_disconnected", "Microsoft delegated account disconnected", {})
    return RedirectResponse(url=f"/settings/teams?notice={quote('Microsoft hesabi baglantisi kaldirildi.')}", status_code=status.HTTP_302_FOUND)


@router.post("/settings/teams/fetch-chats", response_class=HTMLResponse, response_model=None)
def fetch_team_chats(request: Request) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect

    available_targets, graph_subscriptions, graph_errors = load_teams_settings_data(fetch_targets=True)
    if available_targets:
        notice = f"{len(available_targets)} chat bulundu."
    elif graph_errors:
        notice = ""
    else:
        notice = "Bagli hesap icin goruntulenebilir chat bulunamadi."

    return _render_teams_settings(
        request=request,
        notice=notice,
        errors=[],
        fetch_targets=True,
        available_targets=available_targets,
        graph_subscriptions=graph_subscriptions,
        graph_errors=graph_errors,
    )


@router.post("/settings/teams/subscribe", response_class=HTMLResponse, response_model=None)
def subscribe_graph_targets(
    request: Request,
    target_values: list[str] = Form([]),
    manual_chat_reference: str = Form(""),
    manual_chat_label: str = Form(""),
) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect

    effective_target_values = list(target_values)
    errors: list[str] = []
    if manual_chat_reference.strip():
        manual_target, manual_error = build_manual_chat_target(manual_chat_reference, manual_chat_label)
        if manual_target is not None:
            effective_target_values.append(manual_target.value)
        elif manual_error:
            errors.append(manual_error)

    result = subscribe_to_targets(effective_target_values)
    append_activity(
        "graph_subscription_request",
        "Graph chat subscription request processed",
        {"selected_count": len(effective_target_values), "errors": result.errors + errors},
    )
    return _render_teams_settings(request=request, notice=result.notice, errors=result.errors + errors, fetch_targets=False)


@router.post("/settings/teams/labels", response_class=HTMLResponse, response_model=None)
def update_subscription_labels(
    request: Request,
    chat_ids: list[str] = Form([]),
    chat_labels: list[str] = Form([]),
) -> HTMLResponse | RedirectResponse:
    access_redirect = _guard_settings_access(request, "/settings/teams")
    if access_redirect is not None:
        return access_redirect

    label_updates = {chat_id: label for chat_id, label in zip(chat_ids, chat_labels, strict=False)}
    result = save_subscription_labels(label_updates)
    append_activity("graph_labels_saved", "Graph chat labels updated", {"count": len(label_updates)})
    return _render_teams_settings(request=request, notice=result.notice, errors=result.errors, fetch_targets=False)


def _render_dashboard(*, request: Request) -> HTMLResponse:
    settings = get_settings()
    db_ok, db_message = test_database_connection(settings.database_url)
    chat_labels = read_chat_labels(settings.database_url)

    recent_messages: list[TeamsMessage] = []
    messages_error = ""
    db = _maybe_open_session()
    try:
        if db is None:
            messages_error = "Teams mesajlari gosterilemedi; veritabani oturumu acilamadi."
        else:
            recent_messages = list(
                db.scalars(
                    select(TeamsMessage)
                    .options(selectinload(TeamsMessage.triage_result).selectinload(TriageResult.approval_request))
                    .order_by(desc(TeamsMessage.created_at))
                    .limit(20)
                )
            )
    except Exception as exc:  # pragma: no cover
        messages_error = str(exc)
    finally:
        if db is not None:
            db.close()

    return templates.TemplateResponse(
        request=request,
        name="dashboard.html",
        context={
            "db_ok": db_ok,
            "db_message": db_message,
            "recent_messages": recent_messages,
            "recent_logs": get_recent_logs(40),
            "messages_error": messages_error,
            "chat_labels": chat_labels,
            "is_authenticated": _is_authenticated(request),
        },
    )


def _render_general_settings(
    *,
    request: Request,
    notice: str | None,
    db_message: str | None,
    errors: list[str],
) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="settings_general.html",
        context={
            "values": get_general_form_defaults(),
            "config_summary": get_general_config_summary(),
            "notice": notice,
            "db_message": db_message,
            "errors": errors,
            "setup_complete": is_setup_complete(),
            "is_authenticated": _is_authenticated(request),
        },
    )


def _render_teams_settings(
    *,
    request: Request,
    notice: str,
    errors: list[str],
    fetch_targets: bool,
    available_targets: list | None = None,
    graph_subscriptions: list | None = None,
    graph_errors: list[str] | None = None,
) -> HTMLResponse:
    if available_targets is None or graph_subscriptions is None or graph_errors is None:
        available_targets, graph_subscriptions, graph_errors = load_teams_settings_data(fetch_targets=fetch_targets)
    settings = get_settings()
    return templates.TemplateResponse(
        request=request,
        name="settings_teams.html",
        context={
            "values": get_teams_form_defaults(),
            "notice": notice,
            "errors": errors + graph_errors,
            "available_targets": available_targets,
            "graph_subscriptions": graph_subscriptions,
            "fetch_targets": fetch_targets,
            "microsoft_connected": settings.microsoft_delegated_connected,
            "delegated_user": settings.microsoft_delegated_user or "",
            "is_authenticated": _is_authenticated(request),
        },
    )


def _guard_panel_access(request: Request, next_url: str) -> RedirectResponse | None:
    settings = get_settings()
    if settings.panel_auth_configured and not _is_authenticated(request):
        return _redirect_to_login(next_url)
    if not settings.panel_auth_configured:
        return RedirectResponse(url="/settings/general", status_code=status.HTTP_302_FOUND)
    return None


def _guard_settings_access(request: Request, next_url: str) -> RedirectResponse | None:
    settings = get_settings()
    if not settings.panel_auth_configured:
        return None
    if not _is_authenticated(request):
        return _redirect_to_login(next_url)
    return None


def _redirect_to_login(next_url: str) -> RedirectResponse:
    safe_next = _sanitize_next_url(next_url)
    return RedirectResponse(url=f"/login?next={quote(safe_next, safe='/?=&')}", status_code=status.HTTP_302_FOUND)


def _sanitize_next_url(next_url: str | None) -> str:
    if not next_url or not next_url.startswith("/") or next_url.startswith("//"):
        return "/console"
    return next_url


def _is_authenticated(request: Request) -> bool:
    return bool(request.session.get("panel_authenticated"))


def _maybe_open_session() -> Session | None:
    try:
        session_factory = get_session_factory()
        return session_factory()
    except Exception:
        return None


