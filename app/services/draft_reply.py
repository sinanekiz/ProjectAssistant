from __future__ import annotations

from pathlib import Path

from app.adapters.openai_client import OpenAIClient
from app.config import get_settings
from app.db.models import TeamsMessage
from app.schemas.triage import TriageResultJSON

PROMPTS_DIR = Path(__file__).resolve().parents[1] / "prompts"


def generate_reply_draft(*, message: TeamsMessage, triage_payload: TriageResultJSON) -> str | None:
    settings = get_settings()
    client = OpenAIClient(api_key=settings.openai_api_key)
    system_prompt = (PROMPTS_DIR / "reply_system.txt").read_text(encoding="utf-8")
    return client.generate_reply(
        system_prompt=system_prompt,
        message_text=message.message_text,
        summary=triage_payload.summary,
        suggested_action=triage_payload.suggested_action,
        preferred_language=settings.preferred_language,
    )
