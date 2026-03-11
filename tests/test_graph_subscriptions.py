from __future__ import annotations

from app.services.graph_subscriptions import (
    build_manual_chat_target,
    load_teams_settings_data,
    normalize_resource,
    parse_target_value,
    save_subscription_labels,
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


def test_build_manual_chat_target_from_raw_id() -> None:
    target, error = build_manual_chat_target("19:test-thread@thread.v2", "Rahim Build")

    assert error is None
    assert target is not None
    assert target.target_id == "19:test-thread@thread.v2"
    assert target.label == "Rahim Build"


def test_load_teams_settings_data_fetches_targets_only_on_demand(monkeypatch) -> None:
    stub_client = StubGraphClient()
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MICROSOFT_USER_ID", "user-123")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: stub_client)

    targets, subscriptions, errors = load_teams_settings_data(fetch_targets=False)

    assert not errors
    assert targets == []
    assert len(subscriptions) == 1


def test_load_teams_settings_data_fetches_chat_targets_when_requested(monkeypatch) -> None:
    stub_client = StubGraphClient()
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MICROSOFT_USER_ID", "user-123")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: stub_client)

    targets, subscriptions, errors = load_teams_settings_data(fetch_targets=True)

    assert not errors
    assert len(targets) == 2
    assert any(target.label == "Kisi / Sinan - Ayse" for target in targets)
    assert len(subscriptions) == 1


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


def test_load_teams_settings_data_reports_missing_permissions(monkeypatch) -> None:
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setenv("MICROSOFT_USER_ID", "user-123")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: FailingGraphClient())

    targets, subscriptions, errors = load_teams_settings_data(fetch_targets=True)

    assert targets == []
    assert subscriptions == []
    assert errors


def test_save_subscription_labels_returns_notice(monkeypatch) -> None:`r`n    monkeypatch.setattr("app.services.graph_subscriptions.write_chat_labels", lambda database_url, labels: None)`r`n    monkeypatch.setenv("DATABASE_URL", "sqlite://")`r`n`r`n    result = save_subscription_labels({"chat-1": "Rahim Build"})`r`n`r`n    assert "label guncellendi" in result.notice

