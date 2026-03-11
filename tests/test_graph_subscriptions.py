from __future__ import annotations

from app.services.graph_subscriptions import (
    load_graph_console_data,
    normalize_resource,
    parse_target_value,
    subscribe_to_targets,
)


class StubGraphClient:
    def __init__(self) -> None:
        self.created_chats: list[tuple[str, str, str | None]] = []

    def list_user_chats(self, *, user_id: str):
        if user_id != "user-123":
            return []
        return [
            {"id": "chat-1", "chatType": "oneOnOne", "topic": None},
            {"id": "chat-2", "chatType": "group", "topic": "Ops War Room"},
        ]

    def list_chat_members(self, *, chat_id: str):
        if chat_id == "chat-1":
            return [
                {"displayName": "Sinan"},
                {"displayName": "Ayse"},
            ]
        return [
            {"displayName": "Sinan"},
            {"displayName": "Ayse"},
            {"displayName": "Mert"},
        ]

    def list_subscriptions(self):
        return [
            {
                "id": "sub-1",
                "resource": "/chats/chat-1/messages",
                "expirationDateTime": "2026-03-11T12:30:00Z",
            },
        ]

    def create_chat_message_subscription(self, *, chat_id: str, notification_url: str, client_state: str | None = None, expiration_minutes: int = 55):
        self.created_chats.append((chat_id, notification_url, client_state))
        return {"id": f"sub-chat-{len(self.created_chats)}"}


class FailingGraphClient(StubGraphClient):
    def list_user_chats(self, *, user_id: str):
        return None


def test_parse_target_value() -> None:
    parsed = parse_target_value("chat||chat-1||Kisi / Sinan - Ayse")

    assert parsed == ("chat", "chat-1", "Kisi / Sinan - Ayse")


def test_normalize_resource() -> None:
    assert normalize_resource("/Chats/CHAT-1/messages") == "chats/chat-1/messages"


def test_load_graph_console_data_builds_chat_and_subscription_lists(monkeypatch) -> None:
    stub_client = StubGraphClient()
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MICROSOFT_USER_ID", "user-123")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: stub_client)

    targets, subscriptions, errors = load_graph_console_data()

    assert not errors
    assert len(targets) == 2
    assert any(target.label == "Kisi / Sinan - Ayse" for target in targets)
    assert any(target.label == "Grup / Ops War Room" for target in targets)
    assert len(subscriptions) == 1
    assert subscriptions[0].target_type == "chat"


def test_subscribe_to_targets_skips_existing_and_creates_new(monkeypatch) -> None:
    stub_client = StubGraphClient()
    monkeypatch.setenv("PUBLIC_WEBHOOK_BASE_URL", "https://projectassistant.onrender.com")
    monkeypatch.setenv("GRAPH_WEBHOOK_CLIENT_STATE", "state-1")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: stub_client)

    result = subscribe_to_targets([
        "chat||chat-1||Kisi / Sinan - Ayse",
        "chat||chat-2||Grup / Ops War Room",
    ])

    assert "1 chat icin abonelik olusturuldu." in result.notice
    assert "1 chat zaten aboneli listesinde oldugu icin atlandi." in result.notice
    assert len(stub_client.created_chats) == 1
    assert stub_client.created_chats[0][0] == "chat-2"
    assert stub_client.created_chats[0][1] == "https://projectassistant.onrender.com/webhooks/graph"
    assert stub_client.created_chats[0][2] == "state-1"


def test_load_graph_console_data_requires_user_id(monkeypatch) -> None:
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.delenv("MICROSOFT_USER_ID", raising=False)

    targets, subscriptions, errors = load_graph_console_data()

    assert targets == []
    assert subscriptions == []
    assert errors


def test_load_graph_console_data_reports_missing_permissions(monkeypatch) -> None:
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MICROSOFT_USER_ID", "user-123")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: FailingGraphClient())

    targets, subscriptions, errors = load_graph_console_data()

    assert targets == []
    assert subscriptions == []
    assert errors
