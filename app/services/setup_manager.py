from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text

from app.config import get_settings

ROOT_DIR = Path(__file__).resolve().parents[2]
ENV_FILE_PATH = ROOT_DIR / ".env"
REQUIRED_SETUP_KEYS = ("DATABASE_URL", "TARGET_NAME")
SETUP_KEYS = [
    "APP_NAME",
    "APP_ENV",
    "LOG_LEVEL",
    "DATABASE_URL",
    "POSTGRES_DB",
    "POSTGRES_USER",
    "POSTGRES_PASSWORD",
    "POSTGRES_PORT",
    "WATCHED_CHANNELS",
    "RELEVANCE_KEYWORDS",
    "TARGET_NAME",
    "PREFERRED_LANGUAGE",
    "MICROSOFT_TENANT_ID",
    "MICROSOFT_CLIENT_ID",
    "MICROSOFT_CLIENT_SECRET",
    "MICROSOFT_GRAPH_BASE_URL",
    "GRAPH_WEBHOOK_CLIENT_STATE",
    "GRAPH_SUBSCRIPTION_RESOURCE",
    "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA",
    "TEAMS_WEBHOOK_SECRET",
    "TEAMS_BOT_TOKEN",
    "TEAMS_REPLY_URL",
    "TELEGRAM_BOT_TOKEN",
    "TELEGRAM_CHAT_ID",
    "TELEGRAM_APPROVAL_MODE",
    "TELEGRAM_POLL_INTERVAL_SECONDS",
    "PUBLIC_WEBHOOK_BASE_URL",
    "OPENAI_API_KEY",
]
SECRET_KEYS = {
    "POSTGRES_PASSWORD",
    "MICROSOFT_CLIENT_SECRET",
    "TEAMS_WEBHOOK_SECRET",
    "TEAMS_BOT_TOKEN",
    "TELEGRAM_BOT_TOKEN",
    "OPENAI_API_KEY",
}


def read_env_file() -> dict[str, str]:
    if not ENV_FILE_PATH.exists():
        return {}

    values: dict[str, str] = {}
    for line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or "=" not in stripped:
            continue
        key, value = stripped.split("=", 1)
        values[key.strip()] = value.strip()
    return values


def is_setup_complete() -> bool:
    values = read_env_file()
    return all(values.get(key, "").strip() for key in REQUIRED_SETUP_KEYS)


def get_form_defaults() -> dict[str, str]:
    settings = get_settings()
    file_values = read_env_file()
    defaults = {
        "APP_NAME": settings.app_name,
        "APP_ENV": settings.app_env,
        "LOG_LEVEL": settings.log_level,
        "DATABASE_URL": settings.database_url,
        "POSTGRES_DB": settings.postgres_db,
        "POSTGRES_USER": settings.postgres_user,
        "POSTGRES_PASSWORD": settings.postgres_password,
        "POSTGRES_PORT": str(settings.postgres_port),
        "WATCHED_CHANNELS": ", ".join(settings.watched_channels),
        "RELEVANCE_KEYWORDS": ", ".join(settings.relevance_keywords),
        "TARGET_NAME": settings.target_name,
        "PREFERRED_LANGUAGE": settings.preferred_language,
        "MICROSOFT_TENANT_ID": settings.microsoft_tenant_id or "",
        "MICROSOFT_CLIENT_ID": settings.microsoft_client_id or "",
        "MICROSOFT_CLIENT_SECRET": settings.microsoft_client_secret or "",
        "MICROSOFT_GRAPH_BASE_URL": settings.microsoft_graph_base_url,
        "GRAPH_WEBHOOK_CLIENT_STATE": settings.graph_webhook_client_state or "",
        "GRAPH_SUBSCRIPTION_RESOURCE": settings.graph_subscription_resource or "",
        "GRAPH_NOTIFICATION_INCLUDE_RESOURCE_DATA": str(settings.graph_notification_include_resource_data).lower(),
        "TEAMS_WEBHOOK_SECRET": settings.teams_webhook_secret or "",
        "TEAMS_BOT_TOKEN": settings.teams_bot_token or "",
        "TEAMS_REPLY_URL": settings.teams_reply_url or "",
        "TELEGRAM_BOT_TOKEN": settings.telegram_bot_token or "",
        "TELEGRAM_CHAT_ID": settings.telegram_chat_id or "",
        "TELEGRAM_APPROVAL_MODE": settings.telegram_approval_mode,
        "TELEGRAM_POLL_INTERVAL_SECONDS": str(settings.telegram_poll_interval_seconds),
        "PUBLIC_WEBHOOK_BASE_URL": settings.public_webhook_base_url or "",
        "OPENAI_API_KEY": settings.openai_api_key or "",
    }
    defaults.update(file_values)
    return defaults


def save_setup(values: dict[str, Any]) -> None:
    lines: list[str] = []
    for key in SETUP_KEYS:
        value = str(values.get(key, "")).strip()
        lines.append(f"{key}={value}")
    ENV_FILE_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


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


def get_config_summary() -> list[dict[str, str]]:
    summary: list[dict[str, str]] = []
    for key, value in get_form_defaults().items():
        summary.append({"key": key, "value": mask_value(key, value)})
    return summary
