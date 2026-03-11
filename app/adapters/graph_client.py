from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any
import html

import httpx

from app.config import get_settings
from app.logging import get_logger

logger = get_logger(__name__)
DEFAULT_TIMEOUT_SECONDS = 20
GRAPH_DEFAULT_SCOPE = "https://graph.microsoft.com/.default"


@dataclass(slots=True)
class GraphAccessToken:
    access_token: str
    expires_at: datetime


@dataclass(slots=True)
class GraphSendResult:
    success: bool
    message_id: str | None = None
    error: str | None = None
    destination_type: str | None = None


class GraphClient:
    def __init__(
        self,
        *,
        tenant_id: str | None,
        client_id: str | None,
        client_secret: str | None,
        base_url: str,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self._token_cache: GraphAccessToken | None = None

    @classmethod
    def from_settings(cls) -> "GraphClient":
        settings = get_settings()
        return cls(
            tenant_id=settings.microsoft_tenant_id,
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            base_url=settings.microsoft_graph_base_url,
        )

    def get_access_token(self) -> str | None:
        if not self.tenant_id or not self.client_id or not self.client_secret:
            logger.warning("graph_token_skipped_missing_config")
            return None

        if self._token_cache and self._token_cache.expires_at > datetime.now(timezone.utc):
            return self._token_cache.access_token

        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        data = {
            "client_id": self.client_id,
            "client_secret": self.client_secret,
            "scope": GRAPH_DEFAULT_SCOPE,
            "grant_type": "client_credentials",
        }

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(token_url, data=data)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("graph_token_request_failed", extra={"error": str(exc)})
            return None

        payload = response.json()
        access_token = payload.get("access_token")
        expires_in = int(payload.get("expires_in", 3600))
        if not access_token:
            logger.warning("graph_token_missing_in_response")
            return None

        self._token_cache = GraphAccessToken(
            access_token=access_token,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 60, 60)),
        )
        return access_token

    def fetch_message_by_resource(self, *, resource: str) -> dict[str, Any] | None:
        access_token = self.get_access_token()
        if access_token is None:
            return None

        resource_path = resource.lstrip("/")
        url = f"{self.base_url}/{resource_path}"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("graph_fetch_message_failed", extra={"resource": resource, "error": str(exc)})
            return None

        return response.json()

    def fetch_message_details(
        self,
        *,
        team_id: str,
        channel_id: str,
        message_id: str,
        reply_id: str | None = None,
    ) -> dict[str, Any] | None:
        resource = f"teams/{team_id}/channels/{channel_id}/messages/{message_id}"
        if reply_id:
            resource = f"{resource}/replies/{reply_id}"
        return self.fetch_message_by_resource(resource=resource)

    def send_chat_message(self, *, chat_id: str, text: str) -> GraphSendResult:
        return self._post_graph_message(
            resource=f"chats/{chat_id}/messages",
            payload=self._build_message_payload(text),
            destination_type="chat",
            destination_info={"chat_id": chat_id},
        )

    def send_channel_message(self, *, team_id: str, channel_id: str, text: str) -> GraphSendResult:
        return self._post_graph_message(
            resource=f"teams/{team_id}/channels/{channel_id}/messages",
            payload=self._build_message_payload(text),
            destination_type="channel",
            destination_info={"team_id": team_id, "channel_id": channel_id},
        )

    def reply_to_channel_message(self, *, team_id: str, channel_id: str, message_id: str, text: str) -> GraphSendResult:
        return self._post_graph_message(
            resource=f"teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
            payload=self._build_message_payload(text),
            destination_type="channel_reply",
            destination_info={"team_id": team_id, "channel_id": channel_id, "message_id": message_id},
        )

    def _post_graph_message(
        self,
        *,
        resource: str,
        payload: dict[str, Any],
        destination_type: str,
        destination_info: dict[str, str],
    ) -> GraphSendResult:
        access_token = self.get_access_token()
        if access_token is None:
            return GraphSendResult(success=False, error="Microsoft Graph token could not be acquired", destination_type=destination_type)

        url = f"{self.base_url}/{resource.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        logger.info("graph_send_started", extra={"destination_type": destination_type, **destination_info})
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(
                "graph_send_failed",
                extra={"destination_type": destination_type, "error": str(exc), **destination_info},
            )
            return GraphSendResult(success=False, error=str(exc), destination_type=destination_type)

        response_payload = response.json() if response.content else {}
        logger.info("graph_send_succeeded", extra={"destination_type": destination_type, **destination_info})
        return GraphSendResult(
            success=True,
            message_id=response_payload.get("id"),
            destination_type=destination_type,
        )

    def _build_message_payload(self, text: str) -> dict[str, Any]:
        escaped = html.escape(text).replace("\n", "<br>")
        return {
            "body": {
                "contentType": "html",
                "content": f"<div>{escaped}</div>",
            }
        }
