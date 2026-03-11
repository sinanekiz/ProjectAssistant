from __future__ import annotations

from typing import Any

from sqlalchemy import create_engine, text

from app.config import get_settings
from app.services.app_settings import save_database_url, write_runtime_settings

REQUIRED_SETUP_KEYS = ("DATABASE_URL",)
SECRET_KEYS = {
    "MICROSOFT_CLIENT_SECRET",
    "TEAMS_WEBHOOK_SECRET",
    "TEAMS_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "OPENAI_API_KEY",
    "PANEL_LOGIN_PASSWORD",
    "PANEL_SESSION_SECRET",
}
GENERAL_FORM_KEYS = [
    "APP_NAME",
    "APP_ENV",
    "LOG_LEVEL",
    "PREFERRED_LANGUAGE",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_APPROVAL_MODE",
    "TELEGRAM_POLL_INTERVAL_SECONDS",
    "PUBLIC_WEBHOOK_BASE_URL",
    "OPENAI_API_KEY",
    "PANEL_LOGIN_USERNAME",
    "PANEL_LOGIN_PASSWORD",
    "PANEL_SESSION_SECRET",
]
TEAMS_FORM_KEYS = [
    "TARGET_NAME",
    "WATCHED_CHANNELS",
    "RELEVANCE_KEYWORDS",
    "MICROSOFT_TENANT_ID",
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_USER_ID",
    "MICROSOFT_GRAPH_BASE_URL",
    "GRAPH_WEBHOOK_CLIENT_STATE",
    "GRAPH_SUBSCRIPTION_RESOURCE",
    "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA",
    "TEAMS_WEBHOOK_SECRET",
    "TEAMS_BOT_TOKEN",
    "TEAMS_REPLY_URL",
]

_FIELD_MAP = {
    "APP_NAME": "app_name",
    "APP_ENV": "app_env",
    "LOG_LEVEL": "log_level",
    "PREFERRED_LANGUAGE": "preferred_language",
    "TELEGRAM_BOT_TOKEN": "telegram_bot_token",
    "TELEGRAM_CHAT_ID": "telegram_chat_id",
    "TELEGRAM_APPROVAL_MODE": "telegram_approval_mode",
    "TELEGRAM_POLL_INTERVAL_SECONDS": "telegram_poll_interval_seconds",
    "PUBLIC_WEBHOOK_BASE_URL": "public_webhook_base_url",
    "OPENAI_API_KEY": "openai_api_key",
    "PANEL_LOGIN_USERNAME": "panel_login_username",
    "PANEL_LOGIN_PASSWORD": "panel_login_password",
    "PANEL_SESSION_SECRET": "panel_session_secret",
    "TARGET_NAME": "target_name",
    "WATCHED_CHANNELS": "watched_channels",
    "RELEVANCE_KEYWORDS": "relevance_keywords",
    "MICROSOFT_TENANT_ID": "microsoft_tenant_id",
    "MICROSOFT_CLIENT_ID": "microsoft_client_id",
    "MICROSOFT_CLIENT_SECRET": "microsoft_client_secret",
    "MICROSOFT_USER_ID": "microsoft_user_id",
    "MICROSOFT_GRAPH_BASE_URL": "microsoft_graph_base_url",
    "GRAPH_WEBHOOK_CLIENT_STATE": "graph_webhook_client_state",
    "GRAPH_SUBSCRIPTION_RESOURCE": "graph_subscription_resource",
    "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA": "graph_notification_include_resource_data",
    "TEAMS_WEBHOOK_SECRET": "teams_webhook_secret",
    "TEAMS_BOT_TOKEN": "teams_bot_token",
    "TEAMS_REPLY_URL": "teams_reply_url",
}


def is_setup_complete() -> bool:
    settings = get_settings()
    return bool(settings.database_url.strip())


def get_general_form_defaults() -> dict[str, str]:
    settings = get_settings()
    return {
        "DATABASE_URL": settings.database_url,
        "APP_NAME": settings.app_name,
        "APP_ENV": settings.app_env,
        "LOG_LEVEL": settings.log_level,
        "PREFERRED_LANGUAGE": settings.preferred_language,
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token or "",
        "TELEGRAM_CHAT_ID": settings.telegram_chat_id or "",
        "TELEGRAM_APPROVAL_MODE": settings.telegram_approval_mode,
        "TELEGRAM_POLL_INTERVAL_SECONDS": str(settings.telegram_poll_interval_seconds),
        "PUBLIC_WEBHOOK_BASE_URL": settings.public_webhook_base_url or "",
        "OPENAI_API_KEY": settings.openai_api_key or "",
        "PANEL_LOGIN_USERNAME": settings.panel_login_username,
        "PANEL_LOGIN_PASSWORD": settings.panel_login_password or "",
        "PANEL_SESSION_SECRET": settings.panel_session_secret or "",
    }


def get_teams_form_defaults() -> dict[str, str]:
    settings = get_settings()
    return {
        "TARGET_NAME": settings.target_name,
        "WATCHED_CHANNELS": ", ".join(settings.watched_channels),
        "RELEVANCE_KEYWORDS": ", ".join(settings.relevance_keywords),
        "MICROSOFT_TENANT_ID": settings.microsoft_tenant_id or "",
        "MICROSOFT_CLIENT_ID": settings.microsoft_client_id or "",
        "MICROSOFT_CLIENT_SECRET": settings.microsoft_client_secret or "",
        "MICROSOFT_USER_ID": settings.microsoft_user_id or "",
        "MICROSOFT_GRAPH_BASE_URL": settings.microsoft_graph_base_url,
        "GRAPH_WEBHOOK_CLIENT_STATE": settings.graph_webhook_client_state or "",
        "GRAPH_SUBSCRIPTION_RESOURCE": settings.graph_subscription_resource or "",
        "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA": str(settings.graph_notification_include_resource_data).lower(),
        "TEAMS_WEBHOOK_SECRET": settings.teams_webhook_secret or "",
        "TEAMS_BOT_TOKEN": settings.teams_bot_token or "",
        "TEAMS_REPLY_URL": settings.teams_reply_url or "",
    }


def save_general_settings(values: dict[str, Any]) -> None:
    database_url = str(values.get("DATABASE_URL", "")).strip()
    save_database_url(database_url)
    write_runtime_settings(database_url, _map_form_values(values, GENERAL_FORM_KEYS, get_general_form_defaults()))


def save_teams_settings(values: dict[str, Any]) -> None:
    settings = get_settings()
    write_runtime_settings(settings.database_url, _map_form_values(values, TEAMS_FORM_KEYS, get_teams_form_defaults()))


def test_database_connection(database_url: str) -> tuple[bool, str]:
    try:
        engine = create_engine(database_url, pool_pre_ping=True)
        with engine.connect() as connection:
            connection.execute(text("SELECT 1"))
        engine.dispose()
    except Exception as exc:  # pragma: no cover - defensive runtime path
        return False, str(exc)
    return True, "Database connection successful."


def mask_value(key: str, value: str) -> str:
    if not value:
        return ""
    if key in SECRET_KEYS:
        return "*" * min(max(len(value), 8), 16)
    if key == "DATABASE_URL":
        return value.split("@")[-1] if "@" in value else value
    return value


def get_general_config_summary() -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for key, value in get_general_form_defaults().items():
        summary.append({"key": key, "value": mask_value(key, value)})
    return summary


def _map_form_values(values: dict[str, Any], allowed_keys: list[str], defaults: dict[str, str]) -> dict[str, Any]:
    mapped: dict[str, Any] = {}
    for key in allowed_keys:
        if key not in _FIELD_MAP:
            continue
        raw_value = values.get(key, "")
        if isinstance(raw_value, str) and not raw_value.strip() and defaults.get(key):
            mapped[_FIELD_MAP[key]] = defaults[key]
        else:
            mapped[_FIELD_MAP[key]] = raw_value
    return mapped
