from __future__ import annotations

from sqlalchemy import select

from app.adapters.graph_client import GraphSendResult
from app.db.models import ApprovalRequest, SentReply, TeamsMessage, TriageResult


def test_telegram_webhook_approve_updates_approval_status_and_sends_delivery_once(client, session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-telegram",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="root-77",
        message_text="Sinan prod issue var, bakabilir misin?",
        raw_payload={"id": "teams-msg-telegram"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="root-77",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="high",
        confidence=0.94,
        summary="Production issue reported for Sinan.",
        suggested_action="Acknowledge and investigate.",
        suggested_reply="Thanks, I saw this. I will review it shortly.",
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
    db.close()

    monkeypatch.setattr(
        "app.adapters.telegram_client.TelegramClient.answer_callback_query",
        lambda self, **kwargs: True,
    )

    send_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.reply_to_channel_message",
        lambda self, **kwargs: send_calls.append(kwargs) or GraphSendResult(success=True, message_id="graph-reply-1", destination_type="channel_reply"),
    )

    payload = {
        "update_id": 1,
        "callback_query": {
            "id": "callback-1",
            "data": f"approve:{triage_result.id}",
            "message": {
                "message_id": 555,
                "chat": {"id": "123456789", "type": "private"},
            },
        },
    }

    first_response = client.post("/webhooks/telegram", json=payload)
    second_response = client.post("/webhooks/telegram", json=payload)

    assert first_response.status_code == 200
    assert first_response.json()["status"] == "ok"
    assert first_response.json()["approval_status"] == "approved"
    assert first_response.json()["delivery_status"] == "sent"

    assert second_response.status_code == 200
    assert second_response.json()["status"] == "ok"
    assert second_response.json()["approval_status"] == "approved"
    assert second_response.json()["delivery_status"] == "sent"
    assert len(send_calls) == 1

    check_db = session_factory()
    updated = check_db.get(ApprovalRequest, approval_request.id)
    assert updated is not None
    assert updated.status == "approved"
    assert updated.decided_at is not None

    sent_reply = check_db.scalar(select(SentReply).where(SentReply.triage_result_id == triage_result.id))
    assert sent_reply is not None
    assert sent_reply.delivery_status == "sent"


def test_telegram_webhook_approve_persists_failed_delivery(client, session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-failed-delivery",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="root-88",
        message_text="Sinan acil bug var.",
        raw_payload={"id": "teams-msg-failed-delivery"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="root-88",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="critical",
        confidence=0.97,
        summary="Critical production bug reported.",
        suggested_action="Acknowledge and investigate immediately.",
        suggested_reply="Thanks, I saw this. I am checking now.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id="123456789",
        telegram_message_id="777",
        status="pending",
    )
    db.add(approval_request)
    db.commit()
    db.close()

    monkeypatch.setattr(
        "app.adapters.telegram_client.TelegramClient.answer_callback_query",
        lambda self, **kwargs: True,
    )
    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.reply_to_channel_message",
        lambda self, **kwargs: GraphSendResult(success=False, error="boom", destination_type="channel_reply"),
    )

    response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 2,
            "callback_query": {
                "id": "callback-2",
                "data": f"approve:{triage_result.id}",
                "message": {
                    "message_id": 777,
                    "chat": {"id": "123456789", "type": "private"},
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["approval_status"] == "approved"
    assert response.json()["delivery_status"] == "failed"

    check_db = session_factory()
    sent_reply = check_db.scalar(select(SentReply).where(SentReply.triage_result_id == triage_result.id))
    assert sent_reply is not None
    assert sent_reply.delivery_status == "failed"


def test_telegram_webhook_details_sends_detail_message(client, session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-details",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="thread-88",
        message_text="Sinan acil bug var.",
        raw_payload={"id": "teams-msg-details"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="thread-88",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="critical",
        confidence=0.97,
        summary="Critical production bug reported.",
        suggested_action="Acknowledge and investigate immediately.",
        suggested_reply="Thanks, I saw this. I am checking now.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id="123456789",
        telegram_message_id="777",
        status="pending",
    )
    db.add(approval_request)
    db.commit()
    db.close()

    sent_payloads: list[dict[str, object]] = []
    monkeypatch.setattr(
        "app.adapters.telegram_client.TelegramClient.send_message",
        lambda self, **kwargs: sent_payloads.append(kwargs) or None,
    )
    monkeypatch.setattr(
        "app.adapters.telegram_client.TelegramClient.answer_callback_query",
        lambda self, **kwargs: True,
    )

    response = client.post(
        "/webhooks/telegram",
        json={
            "update_id": 3,
            "callback_query": {
                "id": "callback-3",
                "data": f"details:{triage_result.id}",
                "message": {
                    "message_id": 777,
                    "chat": {"id": "123456789", "type": "private"},
                },
            },
        },
    )

    assert response.status_code == 200
    assert response.json()["status"] == "ok"
    assert response.json()["approval_status"] == "pending"
    assert sent_payloads
    assert sent_payloads[0]["chat_id"] == "123456789"

    check_db = session_factory()
    updated = check_db.get(ApprovalRequest, approval_request.id)
    assert updated is not None
    assert updated.status == "pending"

