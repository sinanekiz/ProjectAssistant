from __future__ import annotations

from typing import Any

import httpx

from app.logging import get_logger
from app.schemas.telegram import (
    TelegramGenericResponse,
    TelegramGetUpdatesResponse,
    TelegramMessage,
    TelegramSendMessageResponse,
    TelegramWebhookUpdate,
)

logger = get_logger(__name__)
DEFAULT_TELEGRAM_BASE_URL = "https://api.telegram.org"
DEFAULT_TIMEOUT_SECONDS = 20


class TelegramClient:
    def __init__(
        self,
        *,
        bot_token: str | None,
        base_url: str = DEFAULT_TELEGRAM_BASE_URL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.bot_token = bot_token
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def send_message(
        self,
        *,
        chat_id: str | int | None,
        text: str,
        reply_markup: dict[str, Any] | None = None,
        reply_to_message_id: int | None = None,
    ) -> TelegramMessage | None:
        if not self.bot_token or chat_id is None:
            logger.info("telegram_send_skipped_missing_config")
            return None

        payload: dict[str, Any] = {
            "chat_id": chat_id,
            "text": text,
        }
        if reply_markup is not None:
            payload["reply_markup"] = reply_markup
        if reply_to_message_id is not None:
            payload["reply_to_message_id"] = reply_to_message_id

        response_data = self._post("sendMessage", payload)
        if response_data is None:
            return None

        parsed = TelegramSendMessageResponse.model_validate(response_data)
        if not parsed.ok or parsed.result is None:
            logger.warning("telegram_send_failed", extra={"description": parsed.description})
            return None
        return parsed.result

    def get_updates(self, *, offset: int | None = None, timeout_seconds: int = 15) -> list[TelegramWebhookUpdate] | None:
        if not self.bot_token:
            logger.info("telegram_get_updates_skipped_missing_config")
            return None

        payload: dict[str, Any] = {
            "timeout": timeout_seconds,
            "allowed_updates": ["message", "callback_query"],
        }
        if offset is not None:
            payload["offset"] = offset

        response_data = self._post("getUpdates", payload, timeout_seconds=timeout_seconds + 5)
        if response_data is None:
            return None

        parsed = TelegramGetUpdatesResponse.model_validate(response_data)
        if not parsed.ok:
            logger.warning("telegram_get_updates_failed", extra={"description": parsed.description})
            return None
        return parsed.result

    def answer_callback_query(self, *, callback_query_id: str, text: str) -> bool:
        if not self.bot_token:
            logger.info("telegram_callback_answer_skipped_missing_config")
            return False

        response_data = self._post(
            "answerCallbackQuery",
            {
                "callback_query_id": callback_query_id,
                "text": text,
            },
        )
        if response_data is None:
            return False

        parsed = TelegramGenericResponse.model_validate(response_data)
        if not parsed.ok:
            logger.warning("telegram_callback_answer_failed", extra={"description": parsed.description})
        return parsed.ok

    def _post(
        self,
        method: str,
        payload: dict[str, Any],
        *,
        timeout_seconds: int | None = None,
    ) -> dict[str, Any] | None:
        if not self.bot_token:
            return None

        url = f"{self.base_url}/bot{self.bot_token}/{method}"
        request_timeout = timeout_seconds or self.timeout_seconds
        try:
            with httpx.Client(timeout=request_timeout) as client:
                response = client.post(url, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("telegram_request_failed", extra={"method": method, "error": str(exc)})
            return None
        return response.json()
