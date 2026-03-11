from __future__ import annotations

from dataclasses import dataclass

import httpx

from app.logging import get_logger

logger = get_logger(__name__)
DEFAULT_TIMEOUT_SECONDS = 20


@dataclass(slots=True)
class TeamsSendResult:
    success: bool
    error: str | None = None


class TeamsClient:
    def __init__(
        self,
        *,
        bot_token: str | None,
        reply_url: str | None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.bot_token = bot_token
        self.reply_url = reply_url
        self.timeout_seconds = timeout_seconds

    def send_reply(self, *, channel_id: str | None, thread_id: str | None, reply_text: str) -> TeamsSendResult:
        if not self.reply_url:
            logger.warning("teams_send_skipped_missing_reply_url")
            return TeamsSendResult(success=False, error="TEAMS_REPLY_URL is not configured")
        if not self.bot_token:
            logger.warning("teams_send_skipped_missing_bot_token")
            return TeamsSendResult(success=False, error="TEAMS_BOT_TOKEN is not configured")
        if not channel_id:
            logger.warning("teams_send_skipped_missing_channel_id")
            return TeamsSendResult(success=False, error="channel_id is required")

        payload = {
            "channel_id": channel_id,
            "thread_id": thread_id,
            "reply_text": reply_text,
        }
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(self.reply_url, json=payload, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "teams_send_failed",
                extra={"reply_url": self.reply_url, "error": str(exc), "channel_id": channel_id, "thread_id": thread_id},
            )
            return TeamsSendResult(success=False, error=str(exc))

        logger.info("teams_send_succeeded", extra={"channel_id": channel_id, "thread_id": thread_id})
        return TeamsSendResult(success=True)
