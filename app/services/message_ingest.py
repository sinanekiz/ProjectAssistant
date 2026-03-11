from __future__ import annotations

import html
import re
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.adapters.graph_client import GraphClient
from app.config import get_settings
from app.db.models import GraphNotification, TeamsMessage
from app.logging import get_logger
from app.schemas.common import GraphResourceIdentifiers
from app.schemas.teams import GraphChangeNotificationPayload, GraphChatMessage, GraphNotificationItem, IncomingTeamsWebhook, NormalizedTeamsMessage
from app.services.activity_store import append_activity
from app.services.filters import is_relevant_message

logger = get_logger(__name__)
_CHANNEL_RESOURCE_PATTERNS = (
    re.compile(r"^/?teams/(?P<team_id>[^/]+)/channels/(?P<channel_id>[^/]+)/messages/(?P<message_id>[^/]+)(?:/replies/(?P<reply_id>[^/]+))?$", re.IGNORECASE),
    re.compile(r"^teams\('(?P<team_id>[^']+)'\)/channels\('(?P<channel_id>[^']+)'\)/messages\('(?P<message_id>[^']+)'\)(?:/replies\('(?P<reply_id>[^']+)'\))?$", re.IGNORECASE),
)
_CHAT_RESOURCE_PATTERNS = (
    re.compile(r"^/?chats/(?P<chat_id>[^/]+)/messages/(?P<message_id>[^/]+)$", re.IGNORECASE),
    re.compile(r"^chats\('(?P<chat_id>[^']+)'\)/messages\('(?P<message_id>[^']+)'\)$", re.IGNORECASE),
)
_HTML_TAG_RE = re.compile(r"<[^>]+>")
_WHITESPACE_RE = re.compile(r"\s+")


@dataclass(slots=True)
class GraphNotificationProcessingResult:
    status: str
    notification_id: int | None
    message_id: int | None
    external_message_id: str | None
    created: bool
    duplicate: bool
    is_relevant: bool
    reasons: list[str]
    change_type: str | None
    resource: str | None


def normalize_teams_payload(payload: dict) -> NormalizedTeamsMessage:
    incoming = IncomingTeamsWebhook.model_validate(payload)
    return NormalizedTeamsMessage(
        external_message_id=incoming.external_message_id,
        sender_name=incoming.sender.resolved_name if incoming.sender else None,
        sender_id=incoming.sender.id if incoming.sender else None,
        channel_id=incoming.channel_id,
        channel_name=incoming.channel_name,
        thread_id=incoming.thread_id,
        message_text=incoming.text.strip(),
        mentions=incoming.mentions,
        raw_payload=payload,
    )


def ingest_teams_message(*, db: Session, payload: dict) -> tuple[TeamsMessage, bool, list[str], bool]:
    normalized = normalize_teams_payload(payload)

    existing = db.scalar(select(TeamsMessage).where(TeamsMessage.external_message_id == normalized.external_message_id))
    if existing is not None:
        logger.info(
            "teams_message_duplicate",
            extra={
                "message_id": existing.id,
                "external_message_id": normalized.external_message_id,
            },
        )
        append_activity(
            "teams_message_duplicate",
            "Duplicate Teams message ignored",
            {"external_message_id": normalized.external_message_id, "message_id": existing.id},
        )
        return existing, False, [], True

    is_relevant, reasons = is_relevant_message(normalized)

    message = TeamsMessage(
        external_message_id=normalized.external_message_id,
        sender_name=normalized.sender_name,
        sender_id=normalized.sender_id,
        channel_id=normalized.channel_id,
        channel_name=normalized.channel_name,
        thread_id=normalized.thread_id,
        message_text=normalized.message_text,
        raw_payload=normalized.raw_payload,
        is_relevant=is_relevant,
        conversation_type=normalized.conversation_type,
        team_id=normalized.team_id,
        chat_id=normalized.chat_id,
        parent_message_id=normalized.parent_message_id,
    )
    db.add(message)
    db.commit()
    db.refresh(message)

    log_event = "teams_message_accepted" if is_relevant else "teams_message_ignored"
    logger.info(
        log_event,
        extra={
            "message_id": message.id,
            "external_message_id": message.external_message_id,
            "channel_id": message.channel_id,
            "channel_name": message.channel_name,
            "sender_id": message.sender_id,
            "is_relevant": message.is_relevant,
            "reasons": reasons,
        },
    )
    append_activity(
        log_event,
        "Relevant Teams message stored" if is_relevant else "Irrelevant Teams message stored",
        {
            "message_id": message.id,
            "external_message_id": message.external_message_id,
            "is_relevant": message.is_relevant,
            "reasons": reasons,
        },
    )

    return message, True, reasons, False


def process_graph_notifications(
    *,
    db: Session,
    payload: dict[str, Any],
    graph_client: GraphClient | None = None,
) -> list[GraphNotificationProcessingResult]:
    notification_payload = GraphChangeNotificationPayload.model_validate(payload)
    client = graph_client or GraphClient.from_settings()
    results: list[GraphNotificationProcessingResult] = []

    for notification in notification_payload.value:
        results.append(process_graph_notification(db=db, notification=notification, graph_client=client))

    return results


def process_graph_notification(
    *,
    db: Session,
    notification: GraphNotificationItem,
    graph_client: GraphClient,
) -> GraphNotificationProcessingResult:
    raw_notification = notification.model_dump(mode="json", by_alias=True, exclude_none=True)
    stored_notification = GraphNotification(
        subscription_id=notification.subscription_id,
        change_type=notification.change_type,
        resource=notification.resource,
        client_state=notification.client_state,
        tenant_id=notification.tenant_id,
        raw_payload=raw_notification,
    )
    db.add(stored_notification)
    db.commit()
    db.refresh(stored_notification)

    settings = get_settings()
    if settings.graph_webhook_client_state and notification.client_state != settings.graph_webhook_client_state:
        stored_notification.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.warning(
            "graph_notification_ignored_client_state_mismatch",
            extra={"notification_id": stored_notification.id, "resource": notification.resource},
        )
        append_activity(
            "graph_notification_ignored",
            "Graph notification ignored because client state did not match",
            {"notification_id": stored_notification.id, "resource": notification.resource},
        )
        return GraphNotificationProcessingResult(
            status="ignored_client_state",
            notification_id=stored_notification.id,
            message_id=None,
            external_message_id=None,
            created=False,
            duplicate=False,
            is_relevant=False,
            reasons=[],
            change_type=notification.change_type,
            resource=notification.resource,
        )

    identifiers = extract_graph_resource_identifiers(notification)
    if identifiers is None:
        stored_notification.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.warning(
            "graph_notification_malformed_resource",
            extra={"notification_id": stored_notification.id, "resource": notification.resource},
        )
        append_activity(
            "graph_notification_malformed",
            "Graph notification could not be mapped to message identifiers",
            {"notification_id": stored_notification.id, "resource": notification.resource},
        )
        return GraphNotificationProcessingResult(
            status="invalid_resource",
            notification_id=stored_notification.id,
            message_id=None,
            external_message_id=None,
            created=False,
            duplicate=False,
            is_relevant=False,
            reasons=[],
            change_type=notification.change_type,
            resource=notification.resource,
        )

    message_payload = resolve_graph_message_payload(notification=notification, graph_client=graph_client, identifiers=identifiers)
    if message_payload is None:
        stored_notification.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.warning(
            "graph_message_fetch_failed",
            extra={"notification_id": stored_notification.id, "resource": notification.resource},
        )
        append_activity(
            "graph_message_fetch_failed",
            "Graph notification was stored but message details could not be fetched",
            {"notification_id": stored_notification.id, "resource": notification.resource},
        )
        return GraphNotificationProcessingResult(
            status="message_fetch_failed",
            notification_id=stored_notification.id,
            message_id=None,
            external_message_id=identifiers.external_message_id,
            created=False,
            duplicate=False,
            is_relevant=False,
            reasons=[],
            change_type=notification.change_type,
            resource=notification.resource,
        )

    normalized = normalize_graph_message(notification=notification, message_payload=message_payload)
    existing = db.scalar(select(TeamsMessage).where(TeamsMessage.external_message_id == normalized.external_message_id))
    if existing is not None:
        stored_notification.processed_at = datetime.now(timezone.utc)
        db.commit()
        logger.info(
            "graph_message_duplicate",
            extra={
                "notification_id": stored_notification.id,
                "message_id": existing.id,
                "external_message_id": normalized.external_message_id,
            },
        )
        return GraphNotificationProcessingResult(
            status="duplicate",
            notification_id=stored_notification.id,
            message_id=existing.id,
            external_message_id=normalized.external_message_id,
            created=False,
            duplicate=True,
            is_relevant=existing.is_relevant,
            reasons=[],
            change_type=notification.change_type,
            resource=notification.resource,
        )

    is_relevant, reasons = is_relevant_message(normalized)
    message = TeamsMessage(
        external_message_id=normalized.external_message_id,
        sender_name=normalized.sender_name,
        sender_id=normalized.sender_id,
        channel_id=normalized.channel_id,
        channel_name=normalized.channel_name,
        thread_id=normalized.thread_id,
        message_text=normalized.message_text,
        raw_payload=normalized.raw_payload,
        is_relevant=is_relevant,
        conversation_type=normalized.conversation_type,
        team_id=normalized.team_id,
        chat_id=normalized.chat_id,
        parent_message_id=normalized.parent_message_id,
    )
    db.add(message)
    stored_notification.processed_at = datetime.now(timezone.utc)
    db.commit()
    db.refresh(message)

    log_event = "graph_message_stored" if is_relevant else "graph_message_ignored"
    logger.info(
        log_event,
        extra={
            "notification_id": stored_notification.id,
            "message_id": message.id,
            "external_message_id": message.external_message_id,
            "channel_id": message.channel_id,
            "conversation_type": message.conversation_type,
            "is_relevant": message.is_relevant,
            "reasons": reasons,
        },
    )
    append_activity(
        log_event,
        "Graph Teams message stored" if is_relevant else "Irrelevant Graph Teams message stored",
        {
            "notification_id": stored_notification.id,
            "message_id": message.id,
            "external_message_id": message.external_message_id,
            "is_relevant": message.is_relevant,
            "reasons": reasons,
        },
    )

    return GraphNotificationProcessingResult(
        status="stored",
        notification_id=stored_notification.id,
        message_id=message.id,
        external_message_id=normalized.external_message_id,
        created=True,
        duplicate=False,
        is_relevant=is_relevant,
        reasons=reasons,
        change_type=notification.change_type,
        resource=notification.resource,
    )


def resolve_graph_message_payload(
    *,
    notification: GraphNotificationItem,
    graph_client: GraphClient,
    identifiers: GraphResourceIdentifiers,
) -> dict[str, Any] | None:
    resource_data_payload = notification.resource_data.model_dump(mode="json", by_alias=True, exclude_none=True) if notification.resource_data else {}
    if looks_like_graph_message_payload(resource_data_payload):
        return resource_data_payload

    fetched_payload = graph_client.fetch_message_by_resource(resource=notification.resource)
    if fetched_payload is not None:
        return fetched_payload

    if identifiers.conversation_type == "channel" and identifiers.team_id and identifiers.channel_id:
        return graph_client.fetch_message_details(
            team_id=identifiers.team_id,
            channel_id=identifiers.channel_id,
            message_id=identifiers.message_id,
            reply_id=identifiers.reply_id,
        )
    return None


def extract_graph_resource_identifiers(notification: GraphNotificationItem) -> GraphResourceIdentifiers | None:
    resource_data = notification.resource_data
    resource_message_id = resource_data.id if resource_data and resource_data.id else None
    reply_to_id = resource_data.reply_to_id if resource_data else None
    team_id = resource_data.team_id if resource_data else None
    channel_id = resource_data.channel_id if resource_data else None
    chat_id = resource_data.chat_id if resource_data else None

    for pattern in _CHANNEL_RESOURCE_PATTERNS:
        match = pattern.match(notification.resource)
        if match is None:
            continue
        values = match.groupdict()
        return GraphResourceIdentifiers(
            conversation_type="channel",
            team_id=team_id or values.get("team_id"),
            channel_id=channel_id or values.get("channel_id"),
            message_id=reply_to_id or values["message_id"],
            reply_id=values.get("reply_id") or (resource_message_id if reply_to_id else None),
        )

    for pattern in _CHAT_RESOURCE_PATTERNS:
        match = pattern.match(notification.resource)
        if match is None:
            continue
        values = match.groupdict()
        return GraphResourceIdentifiers(
            conversation_type="chat",
            chat_id=chat_id or values.get("chat_id"),
            message_id=resource_message_id or values["message_id"],
        )

    if resource_message_id and (team_id or channel_id):
        return GraphResourceIdentifiers(
            conversation_type="channel",
            team_id=team_id,
            channel_id=channel_id,
            message_id=reply_to_id or resource_message_id,
            reply_id=resource_message_id if reply_to_id else None,
        )
    if resource_message_id and chat_id:
        return GraphResourceIdentifiers(
            conversation_type="chat",
            chat_id=chat_id,
            message_id=resource_message_id,
        )
    return None


def normalize_graph_message(*, notification: GraphNotificationItem, message_payload: dict[str, Any]) -> NormalizedTeamsMessage:
    graph_message = GraphChatMessage.model_validate(message_payload)
    identifiers = extract_graph_resource_identifiers(notification)
    if identifiers is None:
        raise ValueError("Notification resource could not be mapped to Graph message identifiers")

    team_id = identifiers.team_id
    channel_id = identifiers.channel_id
    channel_name = None
    chat_id = identifiers.chat_id

    if graph_message.channel_identity:
        team_id = team_id or graph_message.channel_identity.team_id
        channel_id = channel_id or graph_message.channel_identity.channel_id
        channel_name = graph_message.channel_identity.channel_display_name
    if graph_message.chat_identity:
        chat_id = chat_id or graph_message.chat_identity.chat_id
    chat_id = chat_id or graph_message.chat_id
    if notification.resource_data:
        team_id = team_id or notification.resource_data.team_id
        channel_id = channel_id or notification.resource_data.channel_id
        channel_name = channel_name or notification.resource_data.channel_name
        chat_id = chat_id or notification.resource_data.chat_id

    message_text = extract_graph_message_text(graph_message)
    mentions = extract_graph_mentions(graph_message)

    raw_payload = {
        "notification": notification.model_dump(mode="json", by_alias=True, exclude_none=True),
        "message": message_payload,
    }
    return NormalizedTeamsMessage(
        external_message_id=identifiers.external_message_id,
        sender_name=graph_message.from_actor.sender_name if graph_message.from_actor else None,
        sender_id=graph_message.from_actor.sender_id if graph_message.from_actor else None,
        channel_id=channel_id,
        channel_name=channel_name,
        thread_id=identifiers.thread_id,
        message_text=message_text,
        mentions=mentions,
        raw_payload=raw_payload,
        conversation_type=identifiers.conversation_type,
        team_id=team_id,
        chat_id=chat_id,
        parent_message_id=identifiers.parent_message_id,
    )


def looks_like_graph_message_payload(payload: dict[str, Any]) -> bool:
    return bool(payload and payload.get("id") and (payload.get("body") or payload.get("from") or payload.get("replyToId") or payload.get("chatId")))


def extract_graph_message_text(message: GraphChatMessage) -> str:
    content = ""
    if message.body and message.body.content:
        content = message.body.content
    if message.body and (message.body.content_type or "").lower() == "html":
        content = _HTML_TAG_RE.sub(" ", content)
    content = html.unescape(content)
    return _WHITESPACE_RE.sub(" ", content).strip()


def extract_graph_mentions(message: GraphChatMessage) -> list[str]:
    mentions: list[str] = []
    for mention in message.mentions:
        if mention.mentioned and mention.mentioned.display_name:
            mentions.append(mention.mentioned.display_name)
        elif mention.mention_text:
            mentions.append(mention.mention_text)
    return mentions
