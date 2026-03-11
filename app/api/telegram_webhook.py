from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, status
from pydantic import ValidationError
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.logging import get_logger
from app.schemas.telegram import TelegramWebhookUpdate
from app.services.approval import handle_telegram_callback, handle_telegram_message

router = APIRouter(prefix="/webhooks/telegram", tags=["telegram"])
logger = get_logger(__name__)


@router.post("", status_code=status.HTTP_200_OK)
def telegram_webhook(payload: dict[str, Any], db: Session = Depends(get_db)) -> dict[str, Any]:
    try:
        update = TelegramWebhookUpdate.model_validate(payload)
    except ValidationError as exc:
        logger.warning("telegram_webhook_invalid_payload", extra={"errors": exc.errors()})
        return {"status": "ignored", "reason": "invalid_payload"}

    if update.callback_query is not None:
        return handle_telegram_callback(db=db, callback_query=update.callback_query)
    if update.message is not None:
        return handle_telegram_message(db=db, telegram_message=update.message)

    logger.info("telegram_webhook_ignored_unsupported_update")
    return {"status": "ignored", "reason": "unsupported_update"}
