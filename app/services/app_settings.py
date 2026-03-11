from __future__ import annotations

from pathlib import Path
from typing import Any

from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

DATABASE_ENV_PATH = Path(__file__).resolve().parents[2] / ".env"
CHAT_LABEL_PREFIX = "graph.chat_label."
DELEGATED_AUTH_KEYS = {
    "microsoft_delegated_access_token",
    "microsoft_delegated_refresh_token",
    "microsoft_delegated_expires_at",
    "microsoft_delegated_scope",
    "microsoft_delegated_user",
}

RUNTIME_SETTING_KEYS = {
    "app_name",
    "app_env",
    "log_level",
    "watched_channels",
    "relevance_keywords",
    "target_name",
    "preferred_language",
    "microsoft_tenant_id",
    "microsoft_client_id",
    "microsoft_client_secret",
    "microsoft_user_id",
    "microsoft_graph_base_url",
    "graph_webhook_client_state",
    "graph_subscription_resource",
    "graph_notification_include_resource_data",
    "teams_webhook_secret",
    "teams_bot_token",
    "teams_reply_url",
    "telegram_bot_token",
    "telegram_chat_id",
    "telegram_approval_mode",
    "telegram_poll_interval_seconds",
    "public_webhook_base_url",
    "openai_api_key",
    "panel_login_username",
    "panel_login_password",
    "panel_session_secret",
    *DELEGATED_AUTH_KEYS,
}

GENERAL_SETTING_KEYS = [
    "app_name",
    "app_env",
    "log_level",
    "preferred_language",
    "telegram_bot_token",
    "telegram_chat_id",
    "telegram_approval_mode",
    "telegram_poll_interval_seconds",
    "public_webhook_base_url",
    "openai_api_key",
    "panel_login_username",
    "panel_login_password",
    "panel_session_secret",
]

TEAMS_SETTING_KEYS = [
    "target_name",
    "watched_channels",
    "relevance_keywords",
    "microsoft_tenant_id",
    "microsoft_client_id",
    "microsoft_client_secret",
    "microsoft_user_id",
    "microsoft_graph_base_url",
    "graph_webhook_client_state",
    "graph_subscription_resource",
    "graph_notification_include_resource_data",
    "teams_webhook_secret",
    "teams_bot_token",
    "teams_reply_url",
]


def read_runtime_settings(database_url: str) -> dict[str, str]:
    return _read_settings(database_url, include_prefix=None)


def read_chat_labels(database_url: str) -> dict[str, str]:
    raw = _read_settings(database_url, include_prefix=CHAT_LABEL_PREFIX)
    return {key.removeprefix(CHAT_LABEL_PREFIX): value for key, value in raw.items()}


def read_named_settings(database_url: str, keys: set[str]) -> dict[str, str]:
    values = read_runtime_settings(database_url)
    return {key: value for key, value in values.items() if key in keys}


def write_runtime_settings(database_url: str, values: dict[str, Any]) -> None:
    filtered = {
        key: _normalize_setting_value(value)
        for key, value in values.items()
        if key in RUNTIME_SETTING_KEYS
    }
    if filtered:
        _write_settings(database_url, filtered)


def write_chat_labels(database_url: str, labels: dict[str, str]) -> None:
    payload = {
        f"{CHAT_LABEL_PREFIX}{chat_id}": label.strip()
        for chat_id, label in labels.items()
        if chat_id.strip() and label.strip()
    }
    if payload:
        _write_settings(database_url, payload)


def write_named_settings(database_url: str, values: dict[str, Any]) -> None:
    payload = {key: _normalize_setting_value(value) for key, value in values.items()}
    if payload:
        _write_settings(database_url, payload)


def delete_settings(database_url: str, keys: list[str]) -> None:
    if not database_url.strip() or not keys:
        return

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            connection.execute(text("DELETE FROM app_settings WHERE key = ANY(:keys)"), {"keys": keys})
    finally:
        engine.dispose()


def save_database_url(database_url: str) -> None:
    DATABASE_ENV_PATH.write_text(f"DATABASE_URL={database_url.strip()}\n", encoding="utf-8")


def _read_settings(database_url: str, include_prefix: str | None) -> dict[str, str]:
    if not database_url.strip():
        return {}

    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.connect() as connection:
            query = "SELECT key, value FROM app_settings"
            params: dict[str, Any] = {}
            if include_prefix is not None:
                query += " WHERE key LIKE :prefix"
                params["prefix"] = f"{include_prefix}%"
            rows = connection.execute(text(query), params).fetchall()
    except SQLAlchemyError:
        return {}
    finally:
        engine.dispose()

    return {str(row[0]): str(row[1]) for row in rows}


def _write_settings(database_url: str, values: dict[str, str]) -> None:
    engine = create_engine(database_url, pool_pre_ping=True)
    try:
        with engine.begin() as connection:
            for key, value in values.items():
                connection.execute(
                    text(
                        """
                        INSERT INTO app_settings (key, value, created_at, updated_at)
                        VALUES (:key, :value, NOW(), NOW())
                        ON CONFLICT (key)
                        DO UPDATE SET value = EXCLUDED.value, updated_at = NOW()
                        """
                    ),
                    {"key": key, "value": value},
                )
    finally:
        engine.dispose()


def _normalize_setting_value(value: Any) -> str:
    if isinstance(value, list):
        return ",".join(str(item).strip() for item in value if str(item).strip())
    return str(value).strip()
