from __future__ import annotations

import pytest
from pydantic import ValidationError

from app.db.models import ApprovalRequest, TeamsMessage
from app.schemas.triage import TriageResultJSON
from app.services.triage import triage_message


def test_triage_schema_rejects_invalid_category() -> None:
    with pytest.raises(ValidationError):
        TriageResultJSON(
            relevant=True,
            category="something_else",
            priority="high",
            confidence=0.9,
            summary="short summary",
            suggested_action="do something",
            suggested_reply="thanks, I will check",
            needs_human_approval=True,
        )


def test_triage_service_stores_result_and_links_approval(session_factory, monkeypatch) -> None:
    db = session_factory()
    message = TeamsMessage(
        external_message_id="teams-msg-triage",
        sender_name="Ayse",
        sender_id="user-1",
        channel_id="engineering-alerts",
        channel_name="Engineering Alerts",
        thread_id="thread-77",
        message_text="Sinan prod issue var, bakabilir misin?",
        raw_payload={"id": "teams-msg-triage"},
        is_relevant=True,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    monkeypatch.setattr(
        "app.adapters.openai_client.OpenAIClient.generate_triage",
        lambda self, **kwargs: TriageResultJSON(
            relevant=True,
            category="bug_report",
            priority="high",
            confidence=0.94,
            summary="Production issue reported for Sinan.",
            suggested_action="Acknowledge and investigate the reported issue.",
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
        lambda **kwargs: ApprovalRequest(id=7, triage_result_id=1, status="pending"),
    )

    result = triage_message(db=db, message=message)

    assert result is not None
    assert result.message_id == message.id
    assert result.category == "bug_report"
    assert result.priority == "high"
    assert result.suggested_reply == "Thanks, I saw this. I will review it shortly."
    assert result.approval_request is not None
    assert result.approval_request.status == "pending"
