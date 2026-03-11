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
        return self._get_graph_json(resource)

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

    def list_teams(self) -> list[dict[str, Any]] | None:
        payload = self._get_graph_json(
            "groups",
            params={
                "$filter": "resourceProvisioningOptions/Any(x:x eq 'Team')",
                "$select": "id,displayName",
                "$top": "200",
            },
        )
        if payload is None:
            return None
        teams = payload.get("value", [])
        teams.sort(key=lambda item: (item.get("displayName") or "").lower())
        return teams

    def list_channels(self, *, team_id: str) -> list[dict[str, Any]] | None:
        payload = self._get_graph_json(
            f"teams/{team_id}/channels",
            params={"$select": "id,displayName,membershipType"},
        )
        if payload is None:
            return None
        channels = payload.get("value", [])
        channels.sort(key=lambda item: (item.get("displayName") or "").lower())
        return channels

    def list_user_chats(self, *, user_id: str) -> list[dict[str, Any]] | None:
        payload = self._get_graph_json(
            f"users/{user_id}/chats",
            params={"$select": "id,topic,chatType,webUrl", "$top": "200"},
        )
        if payload is None:
            return None
        chats = payload.get("value", [])
        chats.sort(key=lambda item: ((item.get("topic") or item.get("id") or "").lower()))
        return chats

    def list_chat_members(self, *, chat_id: str) -> list[dict[str, Any]] | None:
        payload = self._get_graph_json(
            f"chats/{chat_id}/members",
            params={"$select": "displayName,email,userId,roles", "$top": "50"},
        )
        if payload is None:
            return None
        return payload.get("value", [])

    def list_subscriptions(self) -> list[dict[str, Any]] | None:
        payload = self._get_graph_json("subscriptions")
        if payload is None:
            return None
        return payload.get("value", [])

    def create_channel_message_subscription(
        self,
        *,
        team_id: str,
        channel_id: str,
        notification_url: str,
        client_state: str | None = None,
        expiration_minutes: int = 55,
    ) -> dict[str, Any] | None:
        expiration_datetime = datetime.now(timezone.utc) + timedelta(minutes=max(expiration_minutes, 15))
        body: dict[str, Any] = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": f"/teams/{team_id}/channels/{channel_id}/messages",
            "expirationDateTime": expiration_datetime.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        if client_state:
            body["clientState"] = client_state
        return self._post_graph_json("subscriptions", body, "graph_subscription_create", {"target_type": "channel", "team_id": team_id, "channel_id": channel_id})

    def create_chat_message_subscription(
        self,
        *,
        chat_id: str,
        notification_url: str,
        client_state: str | None = None,
        expiration_minutes: int = 55,
    ) -> dict[str, Any] | None:
        expiration_datetime = datetime.now(timezone.utc) + timedelta(minutes=max(expiration_minutes, 15))
        body: dict[str, Any] = {
            "changeType": "created",
            "notificationUrl": notification_url,
            "resource": f"/chats/{chat_id}/messages",
            "expirationDateTime": expiration_datetime.replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        }
        if client_state:
            body["clientState"] = client_state
        return self._post_graph_json("subscriptions", body, "graph_subscription_create", {"target_type": "chat", "chat_id": chat_id})

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

    def _get_graph_json(self, resource: str, params: dict[str, str] | None = None) -> dict[str, Any] | None:
        access_token = self.get_access_token()
        if access_token is None:
            return None

        url = f"{self.base_url}/{resource.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("graph_get_failed", extra={"resource": resource, "error": str(exc)})
            return None

        return response.json()

    def _post_graph_json(
        self,
        resource: str,
        payload: dict[str, Any],
        log_event: str,
        extra_fields: dict[str, str],
    ) -> dict[str, Any] | None:
        access_token = self.get_access_token()
        if access_token is None:
            return None

        url = f"{self.base_url}/{resource.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"{log_event}_started", extra=extra_fields)
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"{log_event}_failed", extra={"error": str(exc), **extra_fields})
            return None

        response_payload = response.json() if response.content else {}
        logger.info(f"{log_event}_succeeded", extra=extra_fields)
        return response_payload

    def _post_graph_message(
        self,
        *,
        resource: str,
        payload: dict[str, Any],
        destination_type: str,
        destination_info: dict[str, str],
    ) -> GraphSendResult:
        response_payload = self._post_graph_json(resource, payload, "graph_send", {"destination_type": destination_type, **destination_info})
        if response_payload is None:
            return GraphSendResult(success=False, error="Microsoft Graph request failed", destination_type=destination_type)

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
