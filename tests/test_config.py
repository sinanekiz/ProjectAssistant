from __future__ import annotations

from pathlib import Path

from app.config import get_settings


def test_dotenv_values_override_process_env(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text(
        "OPENAI_API_KEY=file-openai-key\n"
        "TELEGRAM_BOT_TOKEN=file-telegram-token\n"
        "TELEGRAM_CHAT_ID=123456789\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("OPENAI_API_KEY", "env-openai-key")
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "env-telegram-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "999999999")

    get_settings.cache_clear()
    settings = get_settings()

    assert settings.openai_api_key == "file-openai-key"
    assert settings.telegram_bot_token == "file-telegram-token"
    assert settings.telegram_chat_id == "123456789"


def test_get_settings_reloads_updated_dotenv_after_cache_clear(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    env_path = tmp_path / ".env"
    env_path.write_text("OPENAI_API_KEY=first-key\n", encoding="utf-8")

    get_settings.cache_clear()
    first = get_settings()
    assert first.openai_api_key == "first-key"

    env_path.write_text("OPENAI_API_KEY=second-key\nTELEGRAM_BOT_TOKEN=bot-2\n", encoding="utf-8")

    get_settings.cache_clear()
    second = get_settings()

    assert second.openai_api_key == "second-key"
    assert second.telegram_bot_token == "bot-2"
