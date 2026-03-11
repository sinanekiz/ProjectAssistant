from __future__ import annotations

from json import JSONDecodeError, loads
from pathlib import Path

from fastapi import APIRouter, Form, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import desc, select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.db.models import TeamsMessage, TriageResult
from app.db.session import get_session_factory, reset_db_state
from app.logging import configure_logging, get_recent_logs, get_logger
from app.services.activity_store import append_activity, append_question, list_recent_activity, list_recent_questions
from app.services.message_ingest import ingest_teams_message
from app.services.ops_assistant import answer_manual_question
from app.services.setup_manager import get_config_summary, get_form_defaults, is_setup_complete, save_setup, test_database_connection
from app.services.telegram_polling import refresh_telegram_polling_state
from app.services.triage import triage_message

router = APIRouter(tags=["control-panel"])
TEMPLATES_DIR = Path(__file__).resolve().parents[1] / "ui" / "templates"
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))
logger = get_logger(__name__)


@router.get("/", response_class=HTMLResponse)
def root() -> RedirectResponse:
    target = "/console" if is_setup_complete() else "/setup"
    return RedirectResponse(url=target, status_code=status.HTTP_302_FOUND)


@router.get("/setup", response_class=HTMLResponse)
def setup_page(request: Request, notice: str | None = None, db_message: str | None = None) -> HTMLResponse:
    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={
            "values": get_form_defaults(),
            "notice": notice,
            "db_message": db_message,
            "setup_complete": is_setup_complete(),
        },
    )


@router.post("/setup", response_class=HTMLResponse)
async def save_setup_page(
    request: Request,
    app_name: str = Form("ProjectAssistant"),
    app_env: str = Form("local"),
    log_level: str = Form("INFO"),
    database_url: str = Form(""),
    postgres_db: str = Form("projectassistant"),
    postgres_user: str = Form("projectassistant"),
    postgres_password: str = Form("projectassistant"),
    postgres_port: str = Form("5432"),
    watched_channels: str = Form(""),
    relevance_keywords: str = Form(""),
    target_name: str = Form("Sinan"),
    preferred_language: str = Form("tr"),
    microsoft_tenant_id: str = Form(""),
    microsoft_client_id: str = Form(""),
    microsoft_client_secret: str = Form(""),
    microsoft_graph_base_url: str = Form("https://graph.microsoft.com/v1.0"),
    graph_webhook_client_state: str = Form(""),
    graph_subscription_resource: str = Form(""),
    graph_notification_include_resource_data: str = Form("false"),
    teams_webhook_secret: str = Form(""),
    teams_bot_token: str = Form(""),
    teams_reply_url: str = Form(""),
    telegram_bot_token: str = Form(""),
    telegram_chat_id: str = Form(""),
    telegram_approval_mode: str = Form("polling"),
    telegram_poll_interval_seconds: str = Form("5"),
    public_webhook_base_url: str = Form(""),
    openai_api_key: str = Form(""),
) -> HTMLResponse:
    values = {
        "APP_NAME": app_name,
        "APP_ENV": app_env,
        "LOG_LEVEL": log_level,
        "DATABASE_URL": database_url,
        "POSTGRES_DB": postgres_db,
        "POSTGRES_USER": postgres_user,
        "POSTGRES_PASSWORD": postgres_password,
        "POSTGRES_PORT": postgres_port,
        "WATCHED_CHANNELS": watched_channels,
        "RELEVANCE_KEYWORDS": relevance_keywords,
        "TARGET_NAME": target_name,
        "PREFERRED_LANGUAGE": preferred_language,
        "MICROSOFT_TENANT_ID": microsoft_tenant_id,
        "MICROSOFT_CLIENT_ID": microsoft_client_id,
        "MICROSOFT_CLIENT_SECRET": microsoft_client_secret,
        "MICROSOFT_GRAPH_BASE_URL": microsoft_graph_base_url,
        "GRAPH_WEBHOOK_CLIENT_STATE": graph_webhook_client_state,
        "GRAPH_SUBSCRIPTION_RESOURCE": graph_subscription_resource,
        "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA": graph_notification_include_resource_data,
        "TEAMS_WEBHOOK_SECRET": teams_webhook_secret,
        "TEAMS_BOT_TOKEN": teams_bot_token,
        "TEAMS_REPLY_URL": teams_reply_url,
        "TELEGRAM_BOT_TOKEN": telegram_bot_token,
        "TELEGRAM_CHAT_ID": telegram_chat_id,
        "TELEGRAM_APPROVAL_MODE": telegram_approval_mode,
        "TELEGRAM_POLL_INTERVAL_SECONDS": telegram_poll_interval_seconds,
        "PUBLIC_WEBHOOK_BASE_URL": public_webhook_base_url,
        "OPENAI_API_KEY": openai_api_key,
    }
    save_setup(values)

    from app.config import get_settings as get_cached_settings

    get_cached_settings.cache_clear()
    reset_db_state()
    configure_logging()
    await refresh_telegram_polling_state()

    ok, db_message = test_database_connection(database_url)
    append_activity("setup_saved", "Setup values saved", {"database_ok": ok})
    logger.info("setup_saved", extra={"database_ok": ok})

    return templates.TemplateResponse(
        request=request,
        name="setup.html",
        context={
            "values": get_form_defaults(),
            "notice": "Ayarlar kaydedildi.",
            "db_message": db_message,
            "setup_complete": is_setup_complete(),
        },
    )


@router.get("/console", response_class=HTMLResponse)
def console_page(request: Request) -> HTMLResponse:
    if not is_setup_complete():
        return RedirectResponse(url="/setup", status_code=status.HTTP_302_FOUND)
    return _render_console(request=request)


@router.post("/console/question", response_class=HTMLResponse)
def ask_question(request: Request, question: str = Form("")) -> HTMLResponse:
    if not is_setup_complete():
        return RedirectResponse(url="/setup", status_code=status.HTTP_302_FOUND)

    db = _maybe_open_session()
    try:
        answer = answer_manual_question(question, db=db)
    finally:
        if db is not None:
            db.close()

    append_question(question, answer)
    append_activity("manual_question", "Manual ops question asked", {"question": question})
    return _render_console(request=request, question=question, answer=answer)


@router.post("/console/test-teams", response_class=HTMLResponse)
def test_teams_payload(request: Request, payload_json: str = Form("")) -> HTMLResponse:
    if not is_setup_complete():
        return RedirectResponse(url="/setup", status_code=status.HTTP_302_FOUND)

    test_result = ""
    db = _maybe_open_session()
    if db is None:
        test_result = "DB baglantisi kurulamadigi icin Teams payload testi calistirilamadi."
        return _render_console(request=request, payload_json=payload_json, test_result=test_result)

    try:
        payload = loads(payload_json)
        message, created, reasons, duplicate = ingest_teams_message(db=db, payload=payload)
        triage_result = None
        if created and message.is_relevant:
            triage_result = triage_message(db=db, message=message)

        triage_text = "triage yok"
        approval_text = "approval yok"
        if triage_result is not None:
            triage_text = f"triage_id={triage_result.id}, category={triage_result.category}, priority={triage_result.priority}"
            if triage_result.approval_request is not None:
                approval_text = (
                    f"approval_id={triage_result.approval_request.id}, "
                    f"status={triage_result.approval_request.status}"
                )

        test_result = (
            f"Teams payload islendi. message_id={message.id}, relevant={message.is_relevant}, "
            f"created={created}, duplicate={duplicate}, reasons={', '.join(reasons) or 'none'}, "
            f"{triage_text}, {approval_text}"
        )
        append_activity("manual_teams_test", "Manual Teams payload tested", {"message_id": message.id})
    except JSONDecodeError:
        test_result = "JSON parse edilemedi. Gecerli bir JSON gondermelisin."
    except Exception as exc:  # pragma: no cover - defensive runtime path
        test_result = f"Teams payload islenemedi: {exc}"
    finally:
        db.close()

    return _render_console(request=request, payload_json=payload_json, test_result=test_result)


def _render_console(
    *,
    request: Request,
    question: str = "",
    answer: str = "",
    payload_json: str = "",
    test_result: str = "",
) -> HTMLResponse:
    settings = get_settings()
    db_ok, db_message = test_database_connection(settings.database_url)

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
                    .limit(12)
                )
            )
    except Exception as exc:  # pragma: no cover - defensive runtime path
        messages_error = str(exc)
    finally:
        if db is not None:
            db.close()

    return templates.TemplateResponse(
        request=request,
        name="console.html",
        context={
            "setup_complete": is_setup_complete(),
            "config_summary": get_config_summary(),
            "recent_logs": get_recent_logs(30),
            "recent_activity": list_recent_activity(20),
            "recent_questions": list_recent_questions(12),
            "recent_messages": recent_messages,
            "messages_error": messages_error,
            "db_ok": db_ok,
            "db_message": db_message,
            "question": question,
            "answer": answer,
            "payload_json": payload_json,
            "test_result": test_result,
        },
    )


def _maybe_open_session() -> Session | None:
    try:
        session_factory = get_session_factory()
        return session_factory()
    except Exception:
        return None
