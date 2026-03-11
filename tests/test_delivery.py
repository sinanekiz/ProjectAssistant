from __future__ import annotations

from app.adapters.graph_client import GraphSendResult
from app.db.models import ApprovalRequest, SentReply, TeamsMessage, TriageResult
from app.services.delivery import deliver_approved_reply, resolve_delivery_target


def test_resolve_delivery_target_for_channel_reply() -> None:
    message = TeamsMessage(
        external_message_id="reply-1",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="root-1",
        message_text="Sinan issue var",
        raw_payload={},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="root-1",
    )

    target = resolve_delivery_target(message)

    assert target is not None
    assert target.send_kind == "reply_to_channel_message"
    assert target.team_id == "team-42"
    assert target.channel_id == "channel-99"
    assert target.parent_message_id == "root-1"


def test_resolve_delivery_target_for_chat_message() -> None:
    message = TeamsMessage(
        external_message_id="chat-msg-1",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id=None,
        channel_name=None,
        thread_id="chat-msg-1",
        message_text="Sinan issue var",
        raw_payload={},
        is_relevant=True,
        conversation_type="chat",
        chat_id="chat-123",
    )

    target = resolve_delivery_target(message)

    assert target is not None
    assert target.send_kind == "send_chat_message"
    assert target.chat_id == "chat-123"


def test_deliver_approved_reply_stores_sent_record_for_channel(session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-delivery-success",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="root-1",
        message_text="Sinan issue var",
        raw_payload={"id": "teams-msg-delivery-success"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="root-1",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="high",
        confidence=0.95,
        summary="Issue reported.",
        suggested_action="Investigate.",
        suggested_reply="Gordum, bakiyorum.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id="123456789",
        telegram_message_id="555",
        status="approved",
    )
    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)

    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.reply_to_channel_message",
        lambda self, **kwargs: GraphSendResult(success=True, message_id="graph-reply-1", destination_type="channel_reply"),
    )

    sent_reply = deliver_approved_reply(db=db, approval_request=approval_request)

    assert sent_reply.delivery_status == "sent"
    assert sent_reply.target_channel == "team:team-42:channel:channel-99"
    assert sent_reply.target_thread_id == "root-1"
    assert sent_reply.final_reply_text == "Gordum, bakiyorum."


def test_deliver_approved_reply_stores_sent_record_for_chat(session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="chat-msg-success",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id=None,
        channel_name=None,
        thread_id="chat-msg-success",
        message_text="Sinan issue var",
        raw_payload={"id": "chat-msg-success"},
        is_relevant=True,
        conversation_type="chat",
        chat_id="chat-123",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="internal_question",
        priority="medium",
        confidence=0.91,
        summary="Question reported.",
        suggested_action="Answer the chat.",
        suggested_reply="Gordum, birazdan donecegim.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id="123456789",
        telegram_message_id="555",
        status="approved",
    )
    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)

    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.send_chat_message",
        lambda self, **kwargs: GraphSendResult(success=True, message_id="graph-chat-1", destination_type="chat"),
    )

    sent_reply = deliver_approved_reply(db=db, approval_request=approval_request)

    assert sent_reply.delivery_status == "sent"
    assert sent_reply.target_channel == "chat:chat-123"


def test_deliver_approved_reply_stores_failed_record(session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-delivery-failed",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="channel-99",
        channel_name="Engineering Alerts",
        thread_id="root-2",
        message_text="Sinan issue var",
        raw_payload={"id": "teams-msg-delivery-failed"},
        is_relevant=True,
        conversation_type="channel",
        team_id="team-42",
        parent_message_id="root-2",
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    triage_result = TriageResult(
        message_id=message.id,
        category="bug_report",
        priority="high",
        confidence=0.95,
        summary="Issue reported.",
        suggested_action="Investigate.",
        suggested_reply="Gordum, bakiyorum.",
        needs_human_approval=True,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id="123456789",
        telegram_message_id="555",
        status="approved",
    )
    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)

    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.reply_to_channel_message",
        lambda self, **kwargs: GraphSendResult(success=False, error="boom", destination_type="channel_reply"),
    )

    sent_reply = deliver_approved_reply(db=db, approval_request=approval_request)

    assert sent_reply.delivery_status == "failed"

    persisted = db.get(SentReply, sent_reply.id)
    assert persisted is not None
    assert persisted.delivery_status == "failed"
