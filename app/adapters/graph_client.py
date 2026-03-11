from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Literal
import html
from urllib.parse import urlencode

import httpx

from app.config import get_settings
from app.logging import get_logger
from app.services.app_settings import delete_settings, write_named_settings

logger = get_logger(__name__)
DEFAULT_TIMEOUT_SECONDS = 20
GRAPH_DEFAULT_SCOPE = "https://graph.microsoft.com/.default"
GRAPH_DELEGATED_SCOPES = [
    "offline_access",
    "openid",
    "profile",
    "User.Read",
    "Chat.Read",
    "Chat.ReadWrite",
    "ChatMessage.Send",
    "ChannelMessage.Send",
]
DELEGATED_TOKEN_KEYS = [
    "microsoft_delegated_access_token",
    "microsoft_delegated_refresh_token",
    "microsoft_delegated_expires_at",
    "microsoft_delegated_scope",
    "microsoft_delegated_user",
]


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


@dataclass(slots=True)
class GraphDelegatedAuthResult:
    success: bool
    error: str | None = None
    connected_user: str | None = None


class GraphClient:
    def __init__(
        self,
        *,
        database_url: str,
        tenant_id: str | None,
        client_id: str | None,
        client_secret: str | None,
        base_url: str,
        delegated_access_token: str | None = None,
        delegated_refresh_token: str | None = None,
        delegated_expires_at: str | None = None,
        delegated_user: str | None = None,
        delegated_scope: str | None = None,
        timeout_seconds: int = DEFAULT_TIMEOUT_SECONDS,
    ) -> None:
        self.database_url = database_url
        self.tenant_id = tenant_id
        self.client_id = client_id
        self.client_secret = client_secret
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds
        self.delegated_access_token = delegated_access_token
        self.delegated_refresh_token = delegated_refresh_token
        self.delegated_expires_at = delegated_expires_at
        self.delegated_user = delegated_user
        self.delegated_scope = delegated_scope
        self._token_cache: GraphAccessToken | None = None

    @classmethod
    def from_settings(cls) -> "GraphClient":
        settings = get_settings()
        return cls(
            database_url=settings.database_url,
            tenant_id=settings.microsoft_tenant_id,
            client_id=settings.microsoft_client_id,
            client_secret=settings.microsoft_client_secret,
            base_url=settings.microsoft_graph_base_url,
            delegated_access_token=settings.microsoft_delegated_access_token,
            delegated_refresh_token=settings.microsoft_delegated_refresh_token,
            delegated_expires_at=settings.microsoft_delegated_expires_at,
            delegated_user=settings.microsoft_delegated_user,
            delegated_scope=settings.microsoft_delegated_scope,
        )

    def build_delegated_authorization_url(self, *, redirect_uri: str, state: str) -> str | None:
        if not self.tenant_id or not self.client_id:
            logger.warning("graph_delegated_authorize_skipped_missing_config")
            return None

        query = urlencode(
            {
                "client_id": self.client_id,
                "response_type": "code",
                "redirect_uri": redirect_uri,
                "response_mode": "query",
                "scope": " ".join(GRAPH_DELEGATED_SCOPES),
                "state": state,
                "prompt": "select_account",
            }
        )
        return f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/authorize?{query}"

    def exchange_delegated_code(self, *, code: str, redirect_uri: str) -> GraphDelegatedAuthResult:
        if not self.client_id or not self.client_secret or not self.tenant_id:
            return GraphDelegatedAuthResult(success=False, error="Microsoft Graph kimlik bilgileri eksik.")

        payload = self._request_token(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri,
                "scope": " ".join(GRAPH_DELEGATED_SCOPES),
            },
            "graph_delegated_token_exchange",
        )
        if payload is None:
            return GraphDelegatedAuthResult(success=False, error="Microsoft login sonucu access token alinamadi.")

        profile = self._get_graph_json("me", access_mode="delegated", override_access_token=payload.get("access_token")) or {}
        connected_user = str(profile.get("userPrincipalName") or profile.get("displayName") or profile.get("id") or "")
        self._persist_delegated_tokens(payload, connected_user)
        return GraphDelegatedAuthResult(success=True, connected_user=connected_user or None)

    def disconnect_delegated_identity(self) -> None:
        delete_settings(self.database_url, DELEGATED_TOKEN_KEYS)
        self.delegated_access_token = None
        self.delegated_refresh_token = None
        self.delegated_expires_at = None
        self.delegated_user = None
        self.delegated_scope = None
        get_settings.cache_clear()

    def get_access_token(self) -> str | None:
        if not self.tenant_id or not self.client_id or not self.client_secret:
            logger.warning("graph_token_skipped_missing_config")
            return None

        if self._token_cache and self._token_cache.expires_at > datetime.now(timezone.utc):
            return self._token_cache.access_token

        payload = self._request_token(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "scope": GRAPH_DEFAULT_SCOPE,
                "grant_type": "client_credentials",
            },
            "graph_token_request",
        )
        if payload is None:
            return None

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

    def get_delegated_access_token(self) -> str | None:
        if self.delegated_access_token and not self._delegated_token_expired():
            return self.delegated_access_token
        if not self.delegated_refresh_token:
            logger.warning("graph_delegated_token_missing")
            return None
        return self._refresh_delegated_access_token()

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

    def list_my_chats(self) -> list[dict[str, Any]] | None:
        payload = self._get_graph_json(
            "me/chats",
            params={"$select": "id,topic,chatType", "$top": "200"},
            access_mode="delegated",
        )
        if payload is None:
            return None
        chats = payload.get("value", [])
        chats.sort(key=lambda item: ((item.get("topic") or item.get("id") or "").lower()))
        return chats

    def list_chat_members(self, *, chat_id: str, access_mode: Literal["app", "delegated"] = "app") -> list[dict[str, Any]] | None:
        payload = self._get_graph_json(
            f"chats/{chat_id}/members",
            params={"$select": "displayName,email,userId,roles", "$top": "50"},
            access_mode=access_mode,
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
            access_mode="delegated",
        )

    def send_channel_message(self, *, team_id: str, channel_id: str, text: str) -> GraphSendResult:
        return self._post_graph_message(
            resource=f"teams/{team_id}/channels/{channel_id}/messages",
            payload=self._build_message_payload(text),
            destination_type="channel",
            destination_info={"team_id": team_id, "channel_id": channel_id},
            access_mode="delegated",
        )

    def reply_to_channel_message(self, *, team_id: str, channel_id: str, message_id: str, text: str) -> GraphSendResult:
        return self._post_graph_message(
            resource=f"teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
            payload=self._build_message_payload(text),
            destination_type="channel_reply",
            destination_info={"team_id": team_id, "channel_id": channel_id, "message_id": message_id},
            access_mode="delegated",
        )

    def _delegated_token_expired(self) -> bool:
        if not self.delegated_expires_at:
            return True
        try:
            expires_at = datetime.fromisoformat(self.delegated_expires_at.replace("Z", "+00:00"))
        except ValueError:
            return True
        return expires_at <= datetime.now(timezone.utc) + timedelta(seconds=60)

    def _refresh_delegated_access_token(self) -> str | None:
        if not self.client_id or not self.client_secret or not self.tenant_id or not self.delegated_refresh_token:
            logger.warning("graph_delegated_refresh_skipped_missing_config")
            return None

        payload = self._request_token(
            {
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "grant_type": "refresh_token",
                "refresh_token": self.delegated_refresh_token,
                "scope": " ".join(GRAPH_DELEGATED_SCOPES),
            },
            "graph_delegated_refresh",
        )
        if payload is None:
            return None

        self._persist_delegated_tokens(payload, self.delegated_user)
        return self.delegated_access_token

    def _persist_delegated_tokens(self, payload: dict[str, Any], connected_user: str | None) -> None:
        access_token = str(payload.get("access_token") or "")
        refresh_token = str(payload.get("refresh_token") or self.delegated_refresh_token or "")
        expires_in = int(payload.get("expires_in", 3600))
        expires_at = datetime.now(timezone.utc) + timedelta(seconds=max(expires_in - 60, 60))
        scope = str(payload.get("scope") or " ".join(GRAPH_DELEGATED_SCOPES))

        self.delegated_access_token = access_token or None
        self.delegated_refresh_token = refresh_token or None
        self.delegated_expires_at = expires_at.isoformat()
        self.delegated_scope = scope
        self.delegated_user = connected_user or self.delegated_user

        write_named_settings(
            self.database_url,
            {
                "microsoft_delegated_access_token": self.delegated_access_token or "",
                "microsoft_delegated_refresh_token": self.delegated_refresh_token or "",
                "microsoft_delegated_expires_at": self.delegated_expires_at or "",
                "microsoft_delegated_scope": self.delegated_scope or "",
                "microsoft_delegated_user": self.delegated_user or "",
            },
        )
        get_settings.cache_clear()

    def _request_token(self, data: dict[str, str], log_event: str) -> dict[str, Any] | None:
        if not self.tenant_id:
            return None
        token_url = f"https://login.microsoftonline.com/{self.tenant_id}/oauth2/v2.0/token"
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(token_url, data=data)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"{log_event}_failed", extra={"error": str(exc)})
            return None
        return response.json()

    def _get_graph_json(
        self,
        resource: str,
        params: dict[str, str] | None = None,
        access_mode: Literal["app", "delegated"] = "app",
        override_access_token: str | None = None,
    ) -> dict[str, Any] | None:
        access_token = override_access_token or self._get_token_for_mode(access_mode)
        if access_token is None:
            return None

        url = f"{self.base_url}/{resource.lstrip('/')}"
        headers = {"Authorization": f"Bearer {access_token}"}

        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.get(url, headers=headers, params=params)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning("graph_get_failed", extra={"resource": resource, "error": str(exc), "access_mode": access_mode})
            return None

        return response.json()

    def _post_graph_json(
        self,
        resource: str,
        payload: dict[str, Any],
        log_event: str,
        extra_fields: dict[str, str],
        access_mode: Literal["app", "delegated"] = "app",
    ) -> dict[str, Any] | None:
        access_token = self._get_token_for_mode(access_mode)
        if access_token is None:
            return None

        url = f"{self.base_url}/{resource.lstrip('/')}"
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
        }

        logger.info(f"{log_event}_started", extra={**extra_fields, "access_mode": access_mode})
        try:
            with httpx.Client(timeout=self.timeout_seconds) as client:
                response = client.post(url, headers=headers, json=payload)
                response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.warning(f"{log_event}_failed", extra={"error": str(exc), **extra_fields, "access_mode": access_mode})
            return None

        response_payload = response.json() if response.content else {}
        logger.info(f"{log_event}_succeeded", extra={**extra_fields, "access_mode": access_mode})
        return response_payload

    def _post_graph_message(
        self,
        *,
        resource: str,
        payload: dict[str, Any],
        destination_type: str,
        destination_info: dict[str, str],
        access_mode: Literal["app", "delegated"] = "app",
    ) -> GraphSendResult:
        access_token = self._get_token_for_mode(access_mode)
        if access_token is None:
            error = "Microsoft delegated identity is not connected" if access_mode == "delegated" else "Microsoft Graph app token is missing"
            return GraphSendResult(success=False, error=error, destination_type=destination_type)

        response_payload = self._post_graph_json(
            resource,
            payload,
            "graph_send",
            {"destination_type": destination_type, **destination_info},
            access_mode=access_mode,
        )
        if response_payload is None:
            return GraphSendResult(success=False, error="Microsoft Graph request failed", destination_type=destination_type)

        return GraphSendResult(
            success=True,
            message_id=response_payload.get("id"),
            destination_type=destination_type,
        )

    def _get_token_for_mode(self, access_mode: Literal["app", "delegated"]) -> str | None:
        if access_mode == "delegated":
            return self.get_delegated_access_token()
        return self.get_access_token()

    def _build_message_payload(self, text: str) -> dict[str, Any]:
        escaped = html.escape(text).replace("\n", "<br>")
        return {
            "body": {
                "contentType": "html",
                "content": f"<div>{escaped}</div>",
            }
        }

