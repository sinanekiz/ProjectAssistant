from __future__ import annotations

from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.openai_client import OpenAIClient
from app.config import get_settings
from app.db.models import TriageResult, TeamsMessage
from app.logging import get_logger
from app.services.activity_store import append_activity
from app.services.approval import create_approval_request
from app.services.draft_reply import generate_reply_draft

logger = get_logger(__name__)
PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def triage_message(*, db: Session, message: TeamsMessage) -> TriageResult | None:
    if not message.is_relevant:
        logger.info("triage_skipped_irrelevant_message", extra={"message_id": message.id})
        return None

    existing = db.scalar(
        select(TriageResult)
        .options(selectinload(TriageResult.approval_request))
        .where(TriageResult.message_id == message.id)
    )
    if existing is not None:
        logger.info("triage_already_exists", extra={"message_id": message.id, "triage_result_id": existing.id})
        if existing.needs_human_approval and existing.approval_request is None:
            existing.approval_request = create_approval_request(db=db, triage_result=existing)
        return existing

    settings = get_settings()
    client = OpenAIClient(api_key=settings.openai_api_key)
    system_prompt = (PROMPTS_DIR / "triage_system.txt").read_text(encoding="utf-8")
    triage_payload = client.generate_triage(
        system_prompt=system_prompt,
        message_text=message.message_text,
        sender_name=message.sender_name,
        channel_name=message.channel_name,
        preferred_language=settings.preferred_language,
    )
    if triage_payload is None:
        logger.warning("triage_failed", extra={"message_id": message.id})
        append_activity("triage_failed", "AI triage failed or was skipped", {"message_id": message.id})
        return None

    drafted_reply = generate_reply_draft(message=message, triage_payload=triage_payload)
    final_reply = drafted_reply or triage_payload.suggested_reply

    triage_result = TriageResult(
        message_id=message.id,
        category=triage_payload.category,
        priority=triage_payload.priority,
        confidence=triage_payload.confidence,
        summary=triage_payload.summary,
        suggested_action=triage_payload.suggested_action,
        suggested_reply=final_reply,
        needs_human_approval=triage_payload.needs_human_approval,
    )
    db.add(triage_result)
    db.commit()
    db.refresh(triage_result)

    logger.info(
        "triage_completed",
        extra={
            "message_id": message.id,
            "triage_result_id": triage_result.id,
            "category": triage_result.category,
            "priority": triage_result.priority,
        },
    )
    append_activity(
        "triage_completed",
        "AI triage stored",
        {
            "message_id": message.id,
            "triage_result_id": triage_result.id,
            "category": triage_result.category,
            "priority": triage_result.priority,
        },
    )

    if triage_result.needs_human_approval:
        triage_result.approval_request = create_approval_request(db=db, triage_result=triage_result)

    return triage_result
