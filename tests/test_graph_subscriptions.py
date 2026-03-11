from __future__ import annotations

from app.services.graph_subscriptions import (
    load_graph_console_data,
    normalize_resource,
    parse_channel_target_value,
    subscribe_to_channels,
)


class StubGraphClient:
    def __init__(self) -> None:
        self.created: list[tuple[str, str, str, str | None]] = []

    def list_teams(self):
        return [
            {"id": "team-1", "displayName": "Engineering"},
            {"id": "team-2", "displayName": "Support"},
        ]

    def list_channels(self, *, team_id: str):
        if team_id == "team-1":
            return [{"id": "channel-1", "displayName": "Alerts", "membershipType": "standard"}]
        return [{"id": "channel-2", "displayName": "Ops", "membershipType": "private"}]

    def list_subscriptions(self):
        return [
            {
                "id": "sub-1",
                "resource": "/teams/team-1/channels/channel-1/messages",
                "expirationDateTime": "2026-03-11T12:00:00Z",
            }
        ]

    def create_channel_message_subscription(self, *, team_id: str, channel_id: str, notification_url: str, client_state: str | None = None, expiration_minutes: int = 55):
        self.created.append((team_id, channel_id, notification_url, client_state))
        return {"id": f"sub-{len(self.created)+1}"}


class FailingGraphClient(StubGraphClient):
    def list_teams(self):
        return None


def test_parse_channel_target_value() -> None:
    parsed = parse_channel_target_value("team-1||channel-1||Engineering||Alerts")

    assert parsed == ("team-1", "channel-1", "Engineering", "Alerts")


def test_normalize_resource() -> None:
    assert normalize_resource("/Teams/TEAM-1/Channels/CHANNEL-1/messages") == "teams/team-1/channels/channel-1/messages"


def test_load_graph_console_data_builds_channel_and_subscription_lists(monkeypatch) -> None:
    stub_client = StubGraphClient()
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: stub_client)

    channels, subscriptions, errors = load_graph_console_data()

    assert not errors
    assert len(channels) == 2
    assert channels[0].label == "Engineering / Alerts (standard)"
    assert len(subscriptions) == 1
    assert subscriptions[0].label == "Engineering / Alerts (standard)"


def test_subscribe_to_channels_skips_existing_subscription(monkeypatch) -> None:
    stub_client = StubGraphClient()
    monkeypatch.setenv("PUBLIC_WEBHOOK_BASE_URL", "https://projectassistant.onrender.com")
    monkeypatch.setenv("GRAPH_WEBHOOK_CLIENT_STATE", "state-1")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: stub_client)

    result = subscribe_to_channels([
        "team-1||channel-1||Engineering||Alerts",
        "team-2||channel-2||Support||Ops",
    ])

    assert "1 kanal icin abonelik olusturuldu." in result.notice
    assert "1 kanal zaten aboneli listesinde oldugu icin atlandi." in result.notice
    assert len(stub_client.created) == 1
    assert stub_client.created[0][0] == "team-2"
    assert stub_client.created[0][2] == "https://projectassistant.onrender.com/webhooks/graph"
    assert stub_client.created[0][3] == "state-1"


def test_load_graph_console_data_reports_missing_permissions(monkeypatch) -> None:
    monkeypatch.setenv("MICROSOFT_TENANT_ID", "tenant")
    monkeypatch.setenv("MICROSOFT_CLIENT_ID", "client")
    monkeypatch.setenv("MICROSOFT_CLIENT_SECRET", "secret")
    monkeypatch.setattr("app.services.graph_subscriptions.GraphClient.from_settings", lambda: FailingGraphClient())

    channels, subscriptions, errors = load_graph_console_data()

    assert channels == []
    assert subscriptions == []
    assert errors
