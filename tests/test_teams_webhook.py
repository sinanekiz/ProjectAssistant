from __future__ import annotations

from app.config import get_settings
from app.db.models import ApprovalRequest
from app.schemas.triage import TriageResultJSON


def test_teams_webhook_persists_relevant_message_stores_triage_and_approval(client, monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "bug,issue,prod")
    monkeypatch.setenv("WATCHED_CHANNELS", "engineering-alerts")
    monkeypatch.setenv("OPENAI_API_KEY", "test-key")
    get_settings.cache_clear()

    monkeypatch.setattr(
        "app.adapters.openai_client.OpenAIClient.generate_triage",
        lambda self, **kwargs: TriageResultJSON(
            relevant=True,
            category="bug_report",
            priority="high",
            confidence=0.91,
            summary="Production issue for Sinan.",
            suggested_action="Acknowledge and investigate.",
            suggested_reply="Thanks, I saw this. I will review it shortly.",
            needs_human_approval=True,
        ),
    )
    monkeypatch.setattr(
        "app.adapters.openai_client.OpenAIClient.generate_reply",
        lambda self, **kwargs: "Thanks, I saw this. I will review it shortly.",
    )
    monkeypatch.setattr(
        "app.services.triage.create_approval_request",
        lambda **kwargs: ApprovalRequest(id=3, triage_result_id=1, status="pending"),
    )

    payload = {
        "id": "teams-msg-1",
        "text": "Sinan prod issue var, bakabilir misin?",
        "channelId": "engineering-alerts",
        "channelName": "Engineering Alerts",
        "replyToId": "thread-1",
        "from": {"id": "user-1", "name": "Ayse"},
        "mentions": ["Sinan"],
    }

    response = client.post("/webhooks/teams", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["is_relevant"] is True
    assert response.json()["triage_status"] == "stored"
    assert response.json()["approval_status"] == "pending"
    assert response.json()["triage_result_id"] >= 1


def test_teams_webhook_accepts_but_marks_irrelevant_message(client, monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "bug,issue")
    monkeypatch.setenv("WATCHED_CHANNELS", "engineering-alerts")
    get_settings.cache_clear()

    payload = {
        "id": "teams-msg-2",
        "text": "hello everyone",
        "channelId": "general",
        "channelName": "General",
        "replyToId": "thread-2",
        "from": {"id": "user-2", "name": "Mert"},
        "mentions": [],
    }

    response = client.post("/webhooks/teams", json=payload)

    assert response.status_code == 202
    assert response.json()["status"] == "accepted"
    assert response.json()["is_relevant"] is False
    assert response.json()["triage_status"] == "not_run"
    assert response.json()["approval_status"] == "not_requested"


def test_teams_webhook_returns_duplicate_for_same_external_id(client, monkeypatch) -> None:
    monkeypatch.setenv("TARGET_NAME", "Sinan")
    monkeypatch.setenv("RELEVANCE_KEYWORDS", "issue")
    monkeypatch.setenv("WATCHED_CHANNELS", "")
    get_settings.cache_clear()

    payload = {
        "id": "teams-msg-dup",
        "text": "Sinan issue var",
        "from": {"id": "user-1", "name": "Ayse"},
    }

    first_response = client.post("/webhooks/teams", json=payload)
    second_response = client.post("/webhooks/teams", json=payload)

    assert first_response.status_code == 202
    assert second_response.status_code == 202
    assert second_response.json()["duplicate"] is True
    assert second_response.json()["created"] is False
