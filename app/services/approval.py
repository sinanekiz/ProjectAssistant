from __future__ import annotations

import re
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.adapters.telegram_client import TelegramClient
from app.config import LanguageCode, TelegramApprovalMode, get_settings
from app.db.models import ApprovalRequest, TriageResult
from app.logging import get_logger
from app.schemas.telegram import ParsedApprovalCallback, TelegramCallbackQuery, TelegramMessage
from app.services.activity_store import append_activity
from app.services.delivery import DELIVERY_FAILED_STATUS, DELIVERY_SENT_STATUS, deliver_approved_reply

logger = get_logger(__name__)
CALLBACK_PATTERN = re.compile(r"^(approve|reject|revise|details):(\d+)$")
COMMAND_PATTERNS = [
    (re.compile(r"^(onayla|approve)\s+#?(\d+)$", re.IGNORECASE), "approve"),
    (re.compile(r"^(reddet|reject)\s+#?(\d+)$", re.IGNORECASE), "reject"),
    (re.compile(r"^(revize|revise)\s+#?(\d+)$", re.IGNORECASE), "revise"),
    (re.compile(r"^(detay|details)\s+#?(\d+)$", re.IGNORECASE), "details"),
]
PENDING_STATUS = "pending"
DELIVERY_SKIPPED_STATUS = "delivery_skipped"
DELIVERY_FAILED_APPROVAL_STATUS = "delivery_failed"
APPROVED_STATUS = "approved"
REJECTED_STATUS = "rejected"
REVISION_REQUESTED_STATUS = "revision_requested"
DETAILS_REQUESTED_STATUS = "details_requested"

TR_TEXT = {
    "approval_title": "Yeni onay istegi",
    "details_title": "Mesaj detaylari",
    "message": "Mesaj",
    "sender": "Gonderen",
    "channel": "Kanal",
    "category": "Kategori",
    "priority": "Oncelik",
    "summary": "Ozet",
    "suggested_reply": "Onerilen yanit",
    "suggested_action": "Onerilen aksiyon",
    "confidence": "Guven",
    "status": "Durum",
    "unknown_sender": "Bilinmeyen gonderen",
    "unknown_channel": "Bilinmeyen kanal",
    "button_approve": "Onayla",
    "button_reject": "Reddet",
    "button_revise": "Revize",
    "button_details": "Detay",
    "callback_approved": "Onaylandi.",
    "callback_rejected": "Reddedildi.",
    "callback_revise": "Manuel revizyon olarak isaretlendi.",
    "callback_details": "Detaylar gonderildi.",
    "callback_not_found": "Onay kaydi bulunamadi.",
    "delivery_sent": "Yanit Microsoft Graph uzerinden Teams'e gonderildi.",
    "delivery_failed": "Onay kaydedildi ama Teams gonderimi basarisiz oldu.",
    "already_approved_sent": "Bu onay daha once islenmis ve yanit zaten Teams'e gonderilmis.",
    "already_approved_failed": "Bu onay daha once islenmis ama Teams gonderimi basarisiz kalmis.",
    "already_processed": "Bu onay kaydi artik beklemede degil.",
    "command_hint": "Asagidaki kisayol tuslarini kullanabilirsin.",
    "command_ignored": "Bu mesaj bir approval komutu olarak anlasilmadi.",
}

EN_TEXT = {
    "approval_title": "New approval request",
    "details_title": "Message details",
    "message": "Message",
    "sender": "Sender",
    "channel": "Channel",
    "category": "Category",
    "priority": "Priority",
    "summary": "Summary",
    "suggested_reply": "Suggested reply",
    "suggested_action": "Suggested action",
    "confidence": "Confidence",
    "status": "Status",
    "unknown_sender": "Unknown sender",
    "unknown_channel": "Unknown channel",
    "button_approve": "Approve",
    "button_reject": "Reject",
    "button_revise": "Revise",
    "button_details": "Details",
    "callback_approved": "Approved.",
    "callback_rejected": "Rejected.",
    "callback_revise": "Marked for manual revision.",
    "callback_details": "Details sent.",
    "callback_not_found": "Approval request not found.",
    "delivery_sent": "Reply was sent to Teams via Microsoft Graph.",
    "delivery_failed": "Approval was saved but Teams delivery failed.",
    "already_approved_sent": "This approval was already processed and the reply was already sent to Teams.",
    "already_approved_failed": "This approval was already processed but Teams delivery previously failed.",
    "already_processed": "This approval request is no longer pending.",
    "command_hint": "You can use the shortcut buttons below.",
    "command_ignored": "This message was not recognized as an approval command.",
}


def create_approval_request(*, db: Session, triage_result: TriageResult) -> ApprovalRequest | None:
    if not triage_result.needs_human_approval:
        logger.info("approval_skipped_no_human_approval", extra={"triage_result_id": triage_result.id})
        return None

    existing = db.scalar(select(ApprovalRequest).where(ApprovalRequest.triage_result_id == triage_result.id))
    if existing is not None:
        logger.info(
            "approval_request_already_exists",
            extra={"approval_request_id": existing.id, "triage_result_id": triage_result.id},
        )
        return existing

    settings = get_settings()
    approval_request = ApprovalRequest(
        triage_result_id=triage_result.id,
        telegram_chat_id=settings.telegram_chat_id,
        status=PENDING_STATUS,
    )
    db.add(approval_request)
    db.commit()
    db.refresh(approval_request)

    if not settings.telegram_bot_token or not settings.telegram_chat_id:
        approval_request.status = DELIVERY_SKIPPED_STATUS
        db.commit()
        db.refresh(approval_request)
        logger.warning(
            "approval_delivery_skipped_missing_config",
            extra={"approval_request_id": approval_request.id, "triage_result_id": triage_result.id},
        )
        append_activity(
            "approval_delivery_skipped",
            "Telegram approval skipped because Telegram config is missing",
            {"approval_request_id": approval_request.id, "triage_result_id": triage_result.id},
        )
        return approval_request

    telegram_client = TelegramClient(bot_token=settings.telegram_bot_token)
    telegram_message = telegram_client.send_message(
        chat_id=settings.telegram_chat_id,
        text=build_approval_message(triage_result, settings.preferred_language, settings.telegram_approval_mode),
        reply_markup=build_approval_keyboard(triage_result.id, settings.preferred_language, settings.telegram_approval_mode),
    )
    if telegram_message is None:
        approval_request.status = DELIVERY_FAILED_APPROVAL_STATUS
        db.commit()
        db.refresh(approval_request)
        logger.warning(
            "approval_delivery_failed",
            extra={"approval_request_id": approval_request.id, "triage_result_id": triage_result.id},
        )
        append_activity(
            "approval_delivery_failed",
            "Telegram approval delivery failed",
            {"approval_request_id": approval_request.id, "triage_result_id": triage_result.id},
        )
        return approval_request

    approval_request.telegram_chat_id = str(telegram_message.chat.id)
    approval_request.telegram_message_id = str(telegram_message.message_id)
    approval_request.status = PENDING_STATUS
    db.commit()
    db.refresh(approval_request)

    logger.info(
        "approval_request_sent",
        extra={
            "approval_request_id": approval_request.id,
            "triage_result_id": triage_result.id,
            "telegram_message_id": approval_request.telegram_message_id,
            "approval_mode": settings.telegram_approval_mode,
        },
    )
    append_activity(
        "approval_request_sent",
        "Telegram approval request sent",
        {
            "approval_request_id": approval_request.id,
            "triage_result_id": triage_result.id,
            "telegram_message_id": approval_request.telegram_message_id,
            "approval_mode": settings.telegram_approval_mode,
        },
    )
    return approval_request


def handle_telegram_callback(*, db: Session, callback_query: TelegramCallbackQuery) -> dict[str, str | int | None]:
    parsed = parse_callback_data(callback_query.data)
    if parsed is None:
        logger.warning("telegram_callback_invalid", extra={"data": callback_query.data})
        return {"status": "ignored", "reason": "invalid_callback"}

    settings = get_settings()
    text_map = _get_text_map(settings.preferred_language)
    approval_request = _load_approval_request(db=db, triage_result_id=parsed.triage_result_id)
    if approval_request is None:
        _answer_callback(callback_query.id, text_map["callback_not_found"])
        logger.warning("telegram_callback_approval_not_found", extra={"triage_result_id": parsed.triage_result_id})
        return {"status": "ignored", "reason": "approval_request_not_found"}

    result = _apply_action(
        db=db,
        approval_request=approval_request,
        action=parsed.action,
        source="callback",
        chat_id=callback_query.message.chat.id if callback_query.message else approval_request.telegram_chat_id,
        reply_to_message_id=callback_query.message.message_id if callback_query.message else None,
    )
    _answer_callback(callback_query.id, result["feedback_text"])
    return {
        "status": result["status"],
        "action": parsed.action,
        "approval_request_id": approval_request.id,
        "approval_status": approval_request.status,
        "delivery_status": result.get("delivery_status"),
    }


def handle_telegram_message(*, db: Session, telegram_message: TelegramMessage) -> dict[str, str | int | None]:
    settings = get_settings()
    text_map = _get_text_map(settings.preferred_language)

    if settings.telegram_chat_id and str(telegram_message.chat.id) != str(settings.telegram_chat_id):
        logger.info("telegram_message_ignored_wrong_chat", extra={"chat_id": telegram_message.chat.id})
        return {"status": "ignored", "reason": "wrong_chat"}

    parsed = parse_command_text(telegram_message.text)
    if parsed is None:
        logger.info("telegram_message_ignored_unrecognized_command", extra={"text": telegram_message.text})
        return {"status": "ignored", "reason": "unrecognized_command", "message": text_map["command_ignored"]}

    approval_request = _load_approval_request(db=db, triage_result_id=parsed.triage_result_id)
    if approval_request is None:
        _send_text(chat_id=telegram_message.chat.id, text=text_map["callback_not_found"])
        logger.warning("telegram_command_approval_not_found", extra={"triage_result_id": parsed.triage_result_id})
        return {"status": "ignored", "reason": "approval_request_not_found"}

    result = _apply_action(
        db=db,
        approval_request=approval_request,
        action=parsed.action,
        source="message",
        chat_id=telegram_message.chat.id,
        reply_to_message_id=telegram_message.message_id,
    )
    return {
        "status": result["status"],
        "action": parsed.action,
        "approval_request_id": approval_request.id,
        "approval_status": approval_request.status,
        "delivery_status": result.get("delivery_status"),
    }


def parse_callback_data(value: str | None) -> ParsedApprovalCallback | None:
    if not value:
        return None
    match = CALLBACK_PATTERN.match(value)
    if match is None:
        return None
    return ParsedApprovalCallback(action=match.group(1), triage_result_id=int(match.group(2)))


def parse_command_text(value: str | None) -> ParsedApprovalCallback | None:
    if not value:
        return None
    normalized = value.strip()
    for pattern, action in COMMAND_PATTERNS:
        match = pattern.match(normalized)
        if match is not None:
            return ParsedApprovalCallback(action=action, triage_result_id=int(match.group(2)))
    return None


def build_approval_message(
    triage_result: TriageResult,
    preferred_language: LanguageCode,
    approval_mode: TelegramApprovalMode,
) -> str:
    text_map = _get_text_map(preferred_language)
    message = triage_result.message
    sender = message.sender_name or text_map["unknown_sender"]
    channel = message.channel_name or message.channel_id or message.chat_id or text_map["unknown_channel"]

    lines = [
        f"{text_map['approval_title']} #{triage_result.id}",
        "--------------------",
        f"{text_map['message']}:",
        message.message_text,
        "--------------------",
        f"{text_map['sender']}: {sender}",
        f"{text_map['channel']}: {channel}",
        f"{text_map['category']}: {triage_result.category}",
        f"{text_map['priority']}: {triage_result.priority}",
        f"{text_map['summary']}: {triage_result.summary}",
        "--------------------",
        f"{text_map['suggested_reply']}:",
        triage_result.suggested_reply,
    ]
    if approval_mode == "polling":
        lines.extend(["--------------------", text_map["command_hint"]])
    return "\n".join(lines)


def build_details_message(approval_request: ApprovalRequest, preferred_language: LanguageCode) -> str:
    text_map = _get_text_map(preferred_language)
    triage_result = approval_request.triage_result
    message = triage_result.message
    channel = message.channel_name or message.channel_id or message.chat_id or text_map["unknown_channel"]
    return "\n".join(
        [
            f"{text_map['details_title']} #{triage_result.id}",
            "--------------------",
            f"{text_map['message']}:",
            message.message_text,
            "--------------------",
            f"{text_map['status']}: {approval_request.status}",
            f"{text_map['sender']}: {message.sender_name or text_map['unknown_sender']}",
            f"{text_map['channel']}: {channel}",
            f"{text_map['category']}: {triage_result.category}",
            f"{text_map['priority']}: {triage_result.priority}",
            f"{text_map['confidence']}: {triage_result.confidence}",
            f"{text_map['summary']}: {triage_result.summary}",
            f"{text_map['suggested_action']}: {triage_result.suggested_action}",
            "--------------------",
            f"{text_map['suggested_reply']}:",
            triage_result.suggested_reply,
        ]
    )


def build_approval_keyboard(
    triage_result_id: int,
    preferred_language: LanguageCode,
    approval_mode: TelegramApprovalMode,
) -> dict[str, object]:
    text_map = _get_text_map(preferred_language)
    if approval_mode == "polling":
        return {
            "keyboard": [
                [
                    {"text": f"{text_map['button_approve']} {triage_result_id}"},
                    {"text": f"{text_map['button_reject']} {triage_result_id}"},
                ],
                [
                    {"text": f"{text_map['button_revise']} {triage_result_id}"},
                    {"text": f"{text_map['button_details']} {triage_result_id}"},
                ],
            ],
            "resize_keyboard": True,
            "one_time_keyboard": True,
        }
    return {
        "inline_keyboard": [
            [
                {"text": text_map["button_approve"], "callback_data": f"approve:{triage_result_id}"},
                {"text": text_map["button_reject"], "callback_data": f"reject:{triage_result_id}"},
            ],
            [
                {"text": text_map["button_revise"], "callback_data": f"revise:{triage_result_id}"},
                {"text": text_map["button_details"], "callback_data": f"details:{triage_result_id}"},
            ],
        ]
    }


def _apply_action(
    *,
    db: Session,
    approval_request: ApprovalRequest,
    action: str,
    source: str,
    chat_id: str | int | None,
    reply_to_message_id: int | None,
) -> dict[str, str | None]:
    settings = get_settings()
    text_map = _get_text_map(settings.preferred_language)
    delivery_status: str | None = None

    if action == "details":
        _send_text(
            chat_id=chat_id,
            text=build_details_message(approval_request, settings.preferred_language),
            reply_to_message_id=reply_to_message_id,
        )
        feedback_text = text_map["callback_details"]
    else:
        if approval_request.status != PENDING_STATUS:
            feedback_text, delivery_status = _build_non_pending_feedback(approval_request=approval_request, action=action, text_map=text_map)
            if source == "message":
                _send_text(chat_id=chat_id, text=feedback_text, reply_to_message_id=reply_to_message_id)
            return {"status": "ok", "feedback_text": feedback_text, "delivery_status": delivery_status}

        status_map = {
            "approve": APPROVED_STATUS,
            "reject": REJECTED_STATUS,
            "revise": REVISION_REQUESTED_STATUS,
        }
        feedback_map = {
            "approve": text_map["callback_approved"],
            "reject": text_map["callback_rejected"],
            "revise": text_map["callback_revise"],
        }
        approval_request.status = status_map[action]
        approval_request.decided_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(approval_request)
        feedback_text = feedback_map[action]

        if action == "approve":
            sent_reply = deliver_approved_reply(db=db, approval_request=approval_request)
            delivery_status = sent_reply.delivery_status
            if delivery_status == DELIVERY_SENT_STATUS:
                feedback_text = f"{feedback_text} {text_map['delivery_sent']}"
            elif delivery_status == DELIVERY_FAILED_STATUS:
                feedback_text = f"{feedback_text} {text_map['delivery_failed']}"

        if source == "message":
            _send_text(chat_id=chat_id, text=feedback_text, reply_to_message_id=reply_to_message_id)

    logger.info(
        "telegram_approval_action_processed",
        extra={
            "approval_request_id": approval_request.id,
            "triage_result_id": approval_request.triage_result_id,
            "action": action,
            "status": approval_request.status,
            "source": source,
            "delivery_status": delivery_status,
        },
    )
    append_activity(
        "telegram_approval_action_processed",
        f"Telegram approval action processed: {action}",
        {
            "approval_request_id": approval_request.id,
            "triage_result_id": approval_request.triage_result_id,
            "status": approval_request.status,
            "source": source,
            "delivery_status": delivery_status,
        },
    )
    return {"status": "ok", "feedback_text": feedback_text, "delivery_status": delivery_status}


def _build_non_pending_feedback(*, approval_request: ApprovalRequest, action: str, text_map: dict[str, str]) -> tuple[str, str | None]:
    sent_reply = approval_request.triage_result.sent_reply
    if action == "approve" and approval_request.status == APPROVED_STATUS and sent_reply is not None:
        if sent_reply.delivery_status == DELIVERY_SENT_STATUS:
            return text_map["already_approved_sent"], DELIVERY_SENT_STATUS
        if sent_reply.delivery_status == DELIVERY_FAILED_STATUS:
            return text_map["already_approved_failed"], DELIVERY_FAILED_STATUS
    return text_map["already_processed"], sent_reply.delivery_status if sent_reply is not None else None


def _load_approval_request(*, db: Session, triage_result_id: int) -> ApprovalRequest | None:
    return db.scalar(
        select(ApprovalRequest)
        .options(
            selectinload(ApprovalRequest.triage_result)
            .selectinload(TriageResult.message),
            selectinload(ApprovalRequest.triage_result)
            .selectinload(TriageResult.sent_reply),
        )
        .where(ApprovalRequest.triage_result_id == triage_result_id)
    )


def _answer_callback(callback_query_id: str, text: str) -> None:
    settings = get_settings()
    telegram_client = TelegramClient(bot_token=settings.telegram_bot_token)
    telegram_client.answer_callback_query(callback_query_id=callback_query_id, text=text)


def _send_text(chat_id: str | int | None, text: str, reply_to_message_id: int | None = None) -> None:
    settings = get_settings()
    telegram_client = TelegramClient(bot_token=settings.telegram_bot_token)
    telegram_client.send_message(chat_id=chat_id, text=text, reply_to_message_id=reply_to_message_id)


def _get_text_map(preferred_language: LanguageCode) -> dict[str, str]:
    if preferred_language == "tr":
        return TR_TEXT
    return EN_TEXT

