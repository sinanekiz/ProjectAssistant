from __future__ import annotations

from app.config import get_settings
from app.schemas.teams import NormalizedTeamsMessage
from app.services.filters import is_relevant_message


def test_is_relevant_when_target_name_keyword_and_mention_match(monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "bug,deploy")
    monkeypatch.setenv("WATCHED_CHANNELS", "engineering-alerts")
    get_settings.cache_clear()

    message = NormalizedTeamsMessage(
        external_message_id="msg-1",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="general",
        channel_name="General",
        thread_id="thread-1",
        message_text="Sinan deploy bug var, bakabilir misin?",
        mentions=["Sinan"],
        raw_payload={},
    )

    relevant, reasons = is_relevant_message(message)

    assert relevant is True
    assert "contains_target_name" in reasons
    assert "mentioned_target_name" in reasons
    assert "contains_keyword" in reasons


def test_is_relevant_when_channel_is_watched(monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "")
    monkeypatch.setenv("WATCHED_CHANNELS", "prod-support")
    get_settings.cache_clear()

    message = NormalizedTeamsMessage(
        external_message_id="msg-2",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="prod-support",
        channel_name="Prod Support",
        thread_id="thread-2",
        message_text="General update",
        mentions=[],
        raw_payload={},
    )

    relevant, reasons = is_relevant_message(message)

    assert relevant is True
    assert reasons == ["watched_channel"]
