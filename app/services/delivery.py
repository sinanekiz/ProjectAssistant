from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.graph_client import GraphClient, GraphSendResult
from app.db.models import ApprovalRequest, SentReply, TeamsMessage, TriageResult
from app.logging import get_logger
from app.services.activity_store import append_activity

logger = get_logger(__name__)
DELIVERY_SENT_STATUS = "sent"
DELIVERY_FAILED_STATUS = "failed"


@dataclass(slots=True)
class DeliveryTarget:
    conversation_type: str
    target_channel: str
    target_thread_id: str | None
    send_kind: str
    team_id: str | None = None
    channel_id: str | None = None
    chat_id: str | None = None
    parent_message_id: str | None = None


def deliver_approved_reply(*, db: Session, approval_request: ApprovalRequest) -> SentReply:
    triage_result = db.scalar(
        select(TriageResult)
        .options(selectinload(TriageResult.message), selectinload(TriageResult.sent_reply))
        .where(TriageResult.id == approval_request.triage_result_id)
    )
    if triage_result is None:
        raise ValueError(f"Triage result not found for approval_request_id={approval_request.id}")

    existing = triage_result.sent_reply
    if existing is not None and existing.delivery_status in {DELIVERY_SENT_STATUS, DELIVERY_FAILED_STATUS}:
        logger.info(
            "delivery_already_recorded",
            extra={
                "triage_result_id": triage_result.id,
                "sent_reply_id": existing.id,
                "delivery_status": existing.delivery_status,
            },
        )
        return existing

    delivery_target = resolve_delivery_target(triage_result.message)
    graph_client = GraphClient.from_settings()

    if delivery_target is None:
        send_result = GraphSendResult(success=False, error="Teams message delivery context could not be resolved")
    else:
        send_result = send_via_graph(
            graph_client=graph_client,
            delivery_target=delivery_target,
            reply_text=triage_result.suggested_reply,
        )

    delivery_status = DELIVERY_SENT_STATUS if send_result.success else DELIVERY_FAILED_STATUS
    target_channel = delivery_target.target_channel if delivery_target is not None else "unknown"
    target_thread_id = delivery_target.target_thread_id if delivery_target is not None else None

    sent_reply = SentReply(
        triage_result_id=triage_result.id,
        target_channel=target_channel,
        target_thread_id=target_thread_id,
        final_reply_text=triage_result.suggested_reply,
        delivery_status=delivery_status,
    )
    db.add(sent_reply)
    db.commit()
    db.refresh(sent_reply)

    if send_result.success:
        logger.info(
            "delivery_sent",
            extra={
                "triage_result_id": triage_result.id,
                "sent_reply_id": sent_reply.id,
                "approval_request_id": approval_request.id,
                "target_channel": target_channel,
                "target_thread_id": target_thread_id,
            },
        )
        append_activity(
            "delivery_sent",
            "Approved reply sent back to Teams via Microsoft Graph",
            {
                "triage_result_id": triage_result.id,
                "sent_reply_id": sent_reply.id,
                "approval_request_id": approval_request.id,
                "target_channel": target_channel,
            },
        )
    else:
        logger.warning(
            "delivery_failed",
            extra={
                "triage_result_id": triage_result.id,
                "sent_reply_id": sent_reply.id,
                "approval_request_id": approval_request.id,
                "target_channel": target_channel,
                "error": send_result.error,
            },
        )
        append_activity(
            "delivery_failed",
            "Approved reply failed to send to Teams via Microsoft Graph",
            {
                "triage_result_id": triage_result.id,
                "sent_reply_id": sent_reply.id,
                "approval_request_id": approval_request.id,
                "target_channel": target_channel,
                "error": send_result.error,
            },
        )

    return sent_reply


def resolve_delivery_target(message: TeamsMessage) -> DeliveryTarget | None:
    if message.conversation_type == "chat" and message.chat_id:
        return DeliveryTarget(
            conversation_type="chat",
            target_channel=f"chat:{message.chat_id}",
            target_thread_id=message.external_message_id,
            send_kind="send_chat_message",
            chat_id=message.chat_id,
        )

    if message.conversation_type == "channel" and message.team_id and message.channel_id:
        parent_message_id = message.parent_message_id or message.thread_id or message.external_message_id
        return DeliveryTarget(
            conversation_type="channel",
            target_channel=f"team:{message.team_id}:channel:{message.channel_id}",
            target_thread_id=parent_message_id,
            send_kind="reply_to_channel_message",
            team_id=message.team_id,
            channel_id=message.channel_id,
            parent_message_id=parent_message_id,
        )

    if message.team_id and message.channel_id:
        parent_message_id = message.parent_message_id or message.thread_id or message.external_message_id
        return DeliveryTarget(
            conversation_type="channel",
            target_channel=f"team:{message.team_id}:channel:{message.channel_id}",
            target_thread_id=parent_message_id,
            send_kind="reply_to_channel_message",
            team_id=message.team_id,
            channel_id=message.channel_id,
            parent_message_id=parent_message_id,
        )

    if message.chat_id:
        return DeliveryTarget(
            conversation_type="chat",
            target_channel=f"chat:{message.chat_id}",
            target_thread_id=message.external_message_id,
            send_kind="send_chat_message",
            chat_id=message.chat_id,
        )

    return None


def send_via_graph(*, graph_client: GraphClient, delivery_target: DeliveryTarget, reply_text: str) -> GraphSendResult:
    if delivery_target.send_kind == "send_chat_message" and delivery_target.chat_id:
        return graph_client.send_chat_message(chat_id=delivery_target.chat_id, text=reply_text)

    if (
        delivery_target.send_kind == "reply_to_channel_message"
        and delivery_target.team_id
        and delivery_target.channel_id
        and delivery_target.parent_message_id
    ):
        return graph_client.reply_to_channel_message(
            team_id=delivery_target.team_id,
            channel_id=delivery_target.channel_id,
            message_id=delivery_target.parent_message_id,
            text=reply_text,
        )

    if delivery_target.team_id and delivery_target.channel_id:
        return graph_client.send_channel_message(
            team_id=delivery_target.team_id,
            channel_id=delivery_target.channel_id,
            text=reply_text,
        )

    return GraphSendResult(success=False, error="Unsupported Teams delivery target")
