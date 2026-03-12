from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class GmailMessageMetadata:
    message_id: str
    subject: str
    sender: str
    date: str


class GmailClient:
    def __init__(self, *, access_token: str, base_url: str = "https://gmail.googleapis.com") -> None:
        self.base_url = base_url.rstrip("/")
        self.access_token = access_token

    def list_messages(self, *, user_id: str = "me", query: str = "", max_results: int = 10) -> list[str]:
        params: dict[str, str] = {"maxResults": str(max_results)}
        if query:
            params["q"] = query
        data = self._get_json(f"/gmail/v1/users/{user_id}/messages", params=params)
        messages = data.get("messages") or []
        return [msg.get("id") for msg in messages if msg.get("id")]

    def get_message_metadata(self, *, user_id: str, message_id: str) -> GmailMessageMetadata:
        params = {
            "format": "metadata",
            "metadataHeaders": ["Subject", "From", "Date"],
        }
        data = self._get_json(f"/gmail/v1/users/{user_id}/messages/{message_id}", params=params)
        headers = {header.get("name"): header.get("value") for header in data.get("payload", {}).get("headers", [])}
        return GmailMessageMetadata(
            message_id=message_id,
            subject=headers.get("Subject", ""),
            sender=headers.get("From", ""),
            date=headers.get("Date", ""),
        )

    def _get_json(self, path: str, params: dict[str, Any] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        headers = {"Authorization": f"Bearer {self.access_token}"}
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=headers, params=params)
        response.raise_for_status()
        return response.json()
