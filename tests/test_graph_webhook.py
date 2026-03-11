from __future__ import annotations


def test_graph_webhook_returns_validation_token(client) -> None:
    response = client.post("/webhooks/graph?validationToken=abc123")

    assert response.status_code == 200
    assert response.text == "abc123"


def test_graph_webhook_accepts_notification_payload_and_stores_message(client, monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "bug,issue,prod")
    monkeypatch.setenv("WATCHED_CHANNELS", "Engineering Alerts")

    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.fetch_message_by_resource",
        lambda self, **kwargs: {
            "id": "message-777",
            "from": {"user": {"id": "user-1", "displayName": "Ayse"}},
            "body": {"contentType": "html", "content": "<div>Sinan prod bug var, bakabilir misin?</div>"},
            "mentions": [{"mentioned": {"user": {"displayName": "Sinan"}}}],
            "channelIdentity": {
                "teamId": "team-42",
                "channelId": "channel-99",
                "channelDisplayName": "Engineering Alerts",
            },
        },
    )

    response = client.post(
        "/webhooks/graph",
        json={
            "value": [
                {
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
            ]
        },
    )

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["notification_count"] == 1
    assert response.json()["stored_count"] == 1
    assert response.json()["results"][0]["status"] == "stored"
    assert response.json()["results"][0]["is_relevant"] is True


def test_graph_webhook_handles_message_fetch_failure(client, monkeypatch) -> None:
    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.fetch_message_by_resource",
        lambda self, **kwargs: None,
    )
    monkeypatch.setattr(
        "app.adapters.graph_client.GraphClient.fetch_message_details",
        lambda self, **kwargs: None,
    )

    response = client.post(
        "/webhooks/graph",
        json={
            "value": [
                {
                    "subscriptionId": "sub-123",
                    "changeType": "created",
                    "resource": "teams/team-42/channels/channel-99/messages/message-888",
                    "tenantId": "tenant-abc",
                    "resourceData": {
                        "id": "message-888",
                        "teamId": "team-42",
                        "channelId": "channel-99",
                    },
                }
            ]
        },
    )

    assert response.status_code == 202
    assert response.json()["results"][0]["status"] == "message_fetch_failed"
