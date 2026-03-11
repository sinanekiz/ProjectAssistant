from __future__ import annotations


async def _noop_refresh() -> None:
    return None


def _configure_panel_auth(monkeypatch) -> None:
    monkeypatch.setenv("PANEL_LOGIN_USERNAME", "sinan")
    monkeypatch.setenv("PANEL_LOGIN_PASSWORD", "super-secret")
    monkeypatch.setenv("PANEL_SESSION_SECRET", "session-secret-123")


def _login(client) -> None:
    response = client.post(
        "/login",
        data={
            "username": "sinan",
            "password": "super-secret",
            "next_url": "/console",
        },
        follow_redirects=False,
    )
    assert response.status_code == 302


def test_root_redirects_to_login_when_not_authenticated(client, monkeypatch) -> None:
    _configure_panel_auth(monkeypatch)

    response = client.get("/", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")


def test_general_settings_page_requires_login(client, monkeypatch) -> None:
    _configure_panel_auth(monkeypatch)

    response = client.get("/settings/general", follow_redirects=False)

    assert response.status_code == 302
    assert response.headers["location"].startswith("/login")


def test_general_settings_post_saves_and_shows_success(client, monkeypatch) -> None:
    _configure_panel_auth(monkeypatch)
    monkeypatch.setattr(
        "app.api.control_panel.test_database_connection",
        lambda database_url: (True, "Database connection successful."),
    )
    monkeypatch.setattr(
        "app.api.control_panel.refresh_telegram_polling_state",
        _noop_refresh,
    )

    _login(client)

    response = client.post(
        "/settings/general",
        data={
            "database_url": "postgresql+psycopg://demo:demo@db:5432/demo",
            "app_name": "ProjectAssistant",
            "app_env": "local",
            "log_level": "INFO",
            "preferred_language": "tr",
            "telegram_bot_token": "bot-token",
            "telegram_chat_id": "123456789",
            "telegram_approval_mode": "webhook",
            "telegram_poll_interval_seconds": "5",
            "public_webhook_base_url": "https://example.test",
            "openai_api_key": "",
            "panel_login_username": "sinan",
            "panel_login_password": "super-secret",
            "panel_session_secret": "session-secret-123",
        },
    )

    assert response.status_code == 200
    assert "Genel ayarlar kaydedildi." in response.text
    assert "Database connection successful." in response.text


def test_dashboard_renders_after_login(client, monkeypatch) -> None:
    _configure_panel_auth(monkeypatch)
    _login(client)

    response = client.get("/console")

    assert response.status_code == 200
    assert "Son gelen mesajlar ve son loglar" in response.text
