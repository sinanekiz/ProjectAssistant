from __future__ import annotations

from app.schemas.teams import GraphChangeNotificationPayload, GraphNotificationItem
from app.services.message_ingest import (
    extract_graph_resource_identifiers,
    normalize_graph_message,
    process_graph_notifications,
)


class StubGraphClient:
    def __init__(self, payload: dict | None = None) -> None:
        self.payload = payload
        self.fetch_calls = 0
        self.detail_calls = 0

    def fetch_message_by_resource(self, *, resource: str) -> dict | None:
        self.fetch_calls += 1
        return self.payload

    def fetch_message_details(self, *, team_id: str, channel_id: str, message_id: str, reply_id: str | None = None) -> dict | None:
        self.detail_calls += 1
        return self.payload


SAMPLE_NOTIFICATION = {
    "subscriptionId": "sub-123",
    "changeType": "created",
    "resource": "teams/team-42/channels/channel-99/messages/message-777",
    "tenantId": "tenant-abc",
    "resourceData": {
        "id": "message-777",
        "teamId": "team-42",
        "channelId": "channel-99",
    },
}

SAMPLE_GRAPH_MESSAGE = {
    "id": "message-777",
    "from": {
        "user": {
            "id": "user-1",
            "displayName": "Ayse",
        }
    },
    "body": {
        "contentType": "html",
        "content": "<div>Sinan prod issue var, bakabilir misin?</div>",
    },
    "mentions": [
        {
            "mentioned": {
                "user": {
                    "displayName": "Sinan",
                }
            }
        }
    ],
    "channelIdentity": {
        "teamId": "team-42",
        "channelId": "channel-99",
        "channelDisplayName": "Engineering Alerts",
    },
}

CHAT_NOTIFICATION = {
    "subscriptionId": "sub-chat-1",
    "changeType": "created",
    "resource": "chats/chat-123/messages/chat-message-1",
    "tenantId": "tenant-abc",
    "resourceData": {
        "id": "chat-message-1",
        "chatId": "chat-123",
    },
}

CHAT_GRAPH_MESSAGE = {
    "id": "chat-message-1",
    "chatId": "chat-123",
    "from": {
        "user": {
            "id": "user-1",
            "displayName": "Ayse",
        }
    },
    "body": {
        "contentType": "html",
        "content": "<div>Sinan musaitsen doner misin?</div>",
    },
}


def test_parse_graph_notification_payload() -> None:
    payload = GraphChangeNotificationPayload.model_validate({"value": [SAMPLE_NOTIFICATION]})

    assert len(payload.value) == 1
    assert payload.value[0].resource == "teams/team-42/channels/channel-99/messages/message-777"
    assert payload.value[0].subscription_id == "sub-123"


def test_extract_graph_resource_identifiers_for_channel_message() -> None:
    notification = GraphNotificationItem.model_validate(SAMPLE_NOTIFICATION)

    identifiers = extract_graph_resource_identifiers(notification)

    assert identifiers is not None
    assert identifiers.conversation_type == "channel"
    assert identifiers.team_id == "team-42"
    assert identifiers.channel_id == "channel-99"
    assert identifiers.message_id == "message-777"
    assert identifiers.external_message_id == "message-777"


def test_extract_graph_resource_identifiers_for_chat_message() -> None:
    notification = GraphNotificationItem.model_validate(CHAT_NOTIFICATION)

    identifiers = extract_graph_resource_identifiers(notification)

    assert identifiers is not None
    assert identifiers.conversation_type == "chat"
    assert identifiers.chat_id == "chat-123"
    assert identifiers.message_id == "chat-message-1"


def test_normalize_graph_message() -> None:
    notification = GraphNotificationItem.model_validate(SAMPLE_NOTIFICATION)

    normalized = normalize_graph_message(notification=notification, message_payload=SAMPLE_GRAPH_MESSAGE)

    assert normalized.external_message_id == "message-777"
    assert normalized.sender_name == "Ayse"
    assert normalized.sender_id == "user-1"
    assert normalized.channel_id == "channel-99"
    assert normalized.channel_name == "Engineering Alerts"
    assert normalized.thread_id == "message-777"
    assert normalized.message_text == "Sinan prod issue var, bakabilir misin?"
    assert normalized.mentions == ["Sinan"]
    assert normalized.conversation_type == "channel"
    assert normalized.team_id == "team-42"
    assert normalized.parent_message_id == "message-777"


def test_normalize_graph_chat_message() -> None:
    notification = GraphNotificationItem.model_validate(CHAT_NOTIFICATION)

    normalized = normalize_graph_message(notification=notification, message_payload=CHAT_GRAPH_MESSAGE)

    assert normalized.external_message_id == "chat-message-1"
    assert normalized.conversation_type == "chat"
    assert normalized.chat_id == "chat-123"
    assert normalized.thread_id == "chat-message-1"
    assert normalized.parent_message_id is None


def test_process_graph_notifications_fetches_message_details_when_notification_is_incomplete(session_factory, monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "bug,issue,prod")
    monkeypatch.setenv("WATCHED_CHANNELS", "Engineering Alerts,channel-99")

    db = session_factory()
    client = StubGraphClient(payload=SAMPLE_GRAPH_MESSAGE)

    results = process_graph_notifications(db=db, payload={"value": [SAMPLE_NOTIFICATION]}, graph_client=client)

    assert len(results) == 1
    assert results[0].status == "stored"
    assert results[0].created is True
    assert results[0].is_relevant is True
    assert client.fetch_calls == 1
