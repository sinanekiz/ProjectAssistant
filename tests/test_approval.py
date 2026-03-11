from __future__ import annotations

from app.adapters.graph_client import GraphSendResult
from app.config import get_settings
from app.db.models import ApprovalRequest, TeamsMessage, TriageResult
from app.schemas.telegram import TelegramChat, TelegramMessage
from app.services.approval import (
    build_approval_keyboard,
    build_approval_message,
    create_approval_request,
    handle_telegram_message,
    parse_callback_data,
    parse_command_text,
)


def test_parse_callback_data_accepts_known_pattern() -> None:
    parsed = parse_callback_data("approve:42")

    assert parsed is not None
    assert parsed.action == "approve"
    assert parsed.triage_result_id == 42


def test_parse_command_text_accepts_turkish_shortcut() -> None:
    parsed = parse_command_text("Onayla 12")

    assert parsed is not None
    assert parsed.action == "approve"
    assert parsed.triage_result_id == 12


def test_build_approval_message_prefers_readable_turkish_layout(session_factory) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-layout",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="engineering-alerts",
        channel_name="Engineering Alerts",
        thread_id="thread-77",
        message_text="Sinan prod bug var, bakabilir misin?",
        raw_payload={"id": "teams-msg-layout"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="thread-77",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="high",
        confidence=0.94,
        summary="Sinan icin production bug bildirildi.",
        suggested_action="Mesaji gorup inceleme baslat.",
        suggested_reply="Gordum, kisa sure icinde bakacagim.",
        needs_human_approval=True,
    )
    triage_result.message = message

    rendered = build_approval_message(triage_result, "tr", "polling")
    keyboard = build_approval_keyboard(12, "tr", "polling")

    assert rendered.startswith("Yeni onay istegi")
    assert "Mesaj:" in rendered
    assert "Sinan prod bug var, bakabilir misin?" in rendered
    assert "Onerilen yanit:" in rendered
    assert "--------------------" in rendered
    assert keyboard["keyboard"][0][0]["text"] == "Onayla 12"


def test_create_approval_request_persists_telegram_ids(session_factory, monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    monkeypatch.setenv("PREFERRED_LANGUAGE", "tr")
    monkeypatch.setenv("TELEGRAM_APPROVAL_MODE", "polling")
    get_settings.cache_clear()

    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-approval",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="engineering-alerts",
        channel_name="Engineering Alerts",
        thread_id="thread-77",
        message_text="Sinan prod issue var, bakabilir misin?",
        raw_payload={"id": "teams-msg-approval"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="thread-77",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="high",
        confidence=0.94,
        summary="Sinan icin production issue bildirildi.",
        suggested_action="Mesaji gorup incelemeye basla.",
        suggested_reply="Gordum, kisa sure icinde bakacagim.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    monkeypatch.setattr(
        "app.adapters.telegram_client.TelegramClient.send_message",
        lambda self, **kwargs: TelegramMessage(message_id=555, chat=TelegramChat(id="123456789")),
    )

    approval_request = create_approval_request(db=db, triage_result=triage_result)

    assert approval_request is not None
    assert approval_request.telegram_chat_id == "123456789"
    assert approval_request.telegram_message_id == "555"
    assert approval_request.status == "pending"


def test_handle_telegram_message_processes_polling_command(session_factory, monkeypatch) -> None:
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "bot-token")
    monkeypatch.setenv("TELEGRAM_CHAT_ID", "123456789")
    monkeypatch.setenv("PREFERRED_LANGUAGE", "tr")
    monkeypatch.setenv("TELEGRAM_APPROVAL_MODE", "polling")
    get_settings.cache_clear()

    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-command",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="thread-77",
        message_text="Sinan prod issue var, bakabilir misin?",
        raw_payload={"id": "teams-msg-command"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="thread-77",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="high",
        confidence=0.94,
        summary="Sinan icin production issue bildirildi.",
        suggested_action="Mesaji gorup incelemeye basla.",
        suggested_reply="Gordum, kisa sure icinde bakacagim.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id="123456789",
        telegram_message_id="555",
        status="pending",
    )
    db.add(approval_request)
    db.commit()

    sent_messages: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.adapters.telegram_client.TelegramClient.send_message",
        lambda self, **kwargs: sent_messages.append(kwargs) or TelegramMessage(message_id=777, chat=TelegramChat(id="123456789")),
    )
    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.reply_to_channel_message",
        lambda self, **kwargs: GraphSendResult(success=True, message_id="graph-reply-1", destination_type="channel_reply"),
    )

    result = handle_telegram_message(
        db=db,
        telegram_message=TelegramMessage(
            message_id=999,
            chat=TelegramChat(id="123456789"),
            text=f"Onayla {triage_result.id}",
        ),
    )

    assert result["status"] == "ok"
    assert result["approval_status"] == "approved"
    assert result["delivery_status"] == "sent"
    assert sent_messages
