from __future__ import annotations


async def _noop_refresh() -> None:
    return None


def test_root_redirects_to_setup_when_env_missing(client) -> None:
    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"] == "/setup"


def test_setup_page_renders(client) -> None:
    response = client.get("/setup")

    assert response.status_code == 200
    assert "Ilk Kurulum" in response.text


def test_setup_post_writes_env_and_shows_success(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.api.control_panel.test_database_connection",
        lambda database_url: (True, "Database connection successful."),
    )
    monkeypatch.setattr(
        "app.api.control_panel.refresh_telegram_polling_state",
        _noop_refresh,
    )

    response = client.post(
        "/setup",
        data={
            "app_name": "ProjectAssistant",
            "app_env": "local",
            "log_level": "INFO",
            "database_url": "postgresql+psycopg://demo:demo@db:5432/demo",
            "postgres_db": "demo",
            "postgres_user": "demo",
            "postgres_password": "secret",
            "postgres_port": "5432",
            "watched_channels": "engineering-alerts,prod-support",
            "relevance_keywords": "bug,issue",
            "target_name": "Sinan",
            "preferred_language": "tr",
            "teams_webhook_secret": "",
            "teams_bot_token": "",
            "teams_reply_url": "",
            "telegram_bot_token": "bot-token",
            "telegram_chat_id": "123456789",
            "telegram_approval_mode": "polling",
            "telegram_poll_interval_seconds": "5",
            "public_webhook_base_url": "https://example.test",
            "openai_api_key": "",
        },
    )

    assert response.status_code == 200
    assert "Ayarlar kaydedildi." in response.text
    assert "Database connection successful." in response.text
