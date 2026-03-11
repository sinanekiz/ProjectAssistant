from __future__ import annotations

from app.config import get_settings
from app.schemas.teams import NormalizedTeamsMessage


def is_relevant_message(message: NormalizedTeamsMessage) -> tuple[bool, list[str]]:
    settings = get_settings()
    reasons: list[str] = []

    target_name = settings.target_name.lower().strip()
    text = message.message_text.lower()
    mentions = {mention.lower() for mention in message.mentions}
    watched_channels = {channel.lower() for channel in settings.watched_channels}
    keywords = {keyword.lower() for keyword in settings.relevance_keywords}

    if target_name and target_name in text:
        reasons.append("contains_target_name")
    if target_name and target_name in mentions:
        reasons.append("mentioned_target_name")
    if any(keyword in text for keyword in keywords):
        reasons.append("contains_keyword")
    if any(candidate and candidate.lower() in watched_channels for candidate in (message.channel_id, message.channel_name)):
        reasons.append("watched_channel")

    return (len(reasons) > 0, reasons)
