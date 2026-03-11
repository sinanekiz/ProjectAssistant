from __future__ import annotations

import json
from typing import Any

import httpx
from pydantic import ValidationError

from app.config import LanguageCode
from app.logging import get_logger
from app.schemas.triage import TriageResultJSON

logger = get_logger(__name__)
DEFAULT_OPENAI_BASE_URL = "https://api.openai.com/v1"
DEFAULT_OPENAI_MODEL = "gpt-4.1-mini"
DEFAULT_TIMEOUT_SECONDS = 20


class OpenAIClient:
    def __init__(
        self,
        *,
        api_key: str | None,
        base_url: str = DEFAULT_OPENAI_BASE_URL,
        model: str = DEFAULT_OPENAI_MODEL,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.model = model
        self.timeout_seconds = timeout_seconds

    def generate_triage(
        self,
        *,
        system_prompt: str,
        message_text: str,
        sender_name: str | None,
        channel_name: str | None,
        preferred_language: LanguageCode,
    ) -> TriageResultJSON | None:
        if not self.api_key:
            logger.info("openai_triage_skipped_missing_api_key")
            return None

        language_name = _language_name(preferred_language)
        user_prompt = (
            f"Sender: {sender_name or 'unknown'}\n"
            f"Channel: {channel_name or 'unknown'}\n"
            f"Message:\n{message_text}\n\n"
            f"Write summary, suggested_action, and suggested_reply in {language_name}.\n"
            "Return only valid JSON that matches the required contract."
        )
        raw_content = self._post_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format={"type": "json_object"},
        )
        if raw_content is None:
            return None

        try:
            return TriageResultJSON.model_validate_json(raw_content)
        except ValidationError as exc:
            logger.warning("openai_triage_validation_failed", extra={"error": str(exc)})
            return None

    def generate_reply(
        self,
        *,
        system_prompt: str,
        message_text: str,
        summary: str,
        suggested_action: str,
        preferred_language: LanguageCode,
    ) -> str | None:
        if not self.api_key:
            logger.info("openai_reply_skipped_missing_api_key")
            return None

        language_name = _language_name(preferred_language)
        user_prompt = (
            f"Original message:\n{message_text}\n\n"
            f"Summary: {summary}\n"
            f"Suggested action: {suggested_action}\n\n"
            f"Draft a short neutral reply in {language_name}. Return plain text only."
        )
        raw_content = self._post_chat_completion(
            system_prompt=system_prompt,
            user_prompt=user_prompt,
            response_format=None,
        )
        if raw_content is None:
            return None
        return raw_content.strip()

    def _post_chat_completion(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_format: dict[str, Any] | None,
    ) -> str | None:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "temperature": 0,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
        }
        if response_format is not None:
            payload["response_format"] = response_format

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("openai_request_failed", extra={"error": str(exc)})
            return None

        data = response.json()
        try:
            content = data["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            logger.warning("openai_response_unexpected", extra={"payload": json.dumps(data, default=str)})
            return None

        if isinstance(content, list):
            return "".join(part.get("text", "") for part in content if isinstance(part, dict))
        return str(content)


def _language_name(preferred_language: LanguageCode) -> str:
    if preferred_language == "tr":
        return "Turkish"
    return "English"
