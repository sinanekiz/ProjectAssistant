from __future__ import annotations

from functools import lru_cache
from typing import Annotated, Any, Literal

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, PydanticBaseSettingsSource, SettingsConfigDict

from app.services.app_settings import read_runtime_settings

LanguageCode = Literal["tr", "en"]
TelegramApprovalMode = Literal["polling", "webhook"]


class Settings(BaseSettings):
    app_name: str = "ProjectAssistant"
    app_env: str = "local"
    log_level: str = "INFO"
    database_url: str = "postgresql+psycopg://projectassistant:projectassistant@localhost:5432/projectassistant"

    postgres_db: str = "projectassistant"
    postgres_user: str = "projectassistant"
    postgres_password: str = "projectassistant"
    postgres_port: int = 5432

    watched_channels: Annotated[list[str], NoDecode] = Field(default_factory=list)
    relevance_keywords: Annotated[list[str], NoDecode] = Field(default_factory=list)
    target_name: str = "Sinan"
    preferred_language: LanguageCode = "tr"

    microsoft_tenant_id: str | None = None
    microsoft_client_id: str | None = None
    microsoft_client_secret: str | None = None
    microsoft_user_id: str | None = None
    microsoft_graph_base_url: str = "https://graph.microsoft.com/v1.0"
    graph_webhook_client_state: str | None = None
    graph_subscription_resource: str | None = None
    graph_notification_include_resource_data: bool = False

    teams_webhook_secret: str | None = None
    teams_bot_token: str | None = None
    teams_reply_url: str | None = None
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    telegram_approval_mode: TelegramApprovalMode = "polling"
    telegram_poll_interval_seconds: int = 5
    public_webhook_base_url: str | None = None
    openai_api_key: str | None = None

    panel_login_username: str = "sinan"
    panel_login_password: str | None = None
    panel_session_secret: str | None = None

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        return (
            init_settings,
            dotenv_settings,
            env_settings,
            file_secret_settings,
        )

    @field_validator("watched_channels", "relevance_keywords", mode="before")
    @classmethod
    def split_csv(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, str):
            return [item.strip() for item in value.split(",") if item.strip()]
        if isinstance(value, list):
            return [str(item).strip() for item in value if str(item).strip()]
        raise TypeError("Expected a comma-separated string or list")

    @property
    def panel_auth_configured(self) -> bool:
        return bool(self.panel_login_password and self.panel_session_secret)


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    base_settings = Settings()
    db_overrides = read_runtime_settings(base_settings.database_url)
    if not db_overrides:
        return base_settings

    merged_values = base_settings.model_dump()
    merged_values.update(db_overrides)
    return Settings.model_validate(merged_values)
