from __future__ import annotations

import asyncio

from app.adapters.telegram_client import TelegramClient
from app.config import get_settings
from app.db.session import get_session_factory
from app.logging import get_logger
from app.services.approval import handle_telegram_message

logger = get_logger(__name__)
_polling_task: asyncio.Task[None] | None = None
_polling_lock = asyncio.Lock()
_polling_offset: int | None = None


async def refresh_telegram_polling_state() -> None:
    settings = get_settings()
    if settings.telegram_approval_mode == "polling" and settings.telegram_bot_token:
        await start_telegram_polling()
        return
    await stop_telegram_polling()


async def start_telegram_polling() -> None:
    global _polling_task

    settings = get_settings()
    if settings.telegram_approval_mode != "polling":
        logger.info("telegram_polling_not_started_wrong_mode", extra={"mode": settings.telegram_approval_mode})
        return
    if not settings.telegram_bot_token:
        logger.info("telegram_polling_not_started_missing_token")
        return

    async with _polling_lock:
        if _polling_task is not None and not _polling_task.done():
            return
        _polling_task = asyncio.create_task(_poll_loop(), name="telegram-polling")
        logger.info("telegram_polling_started")


async def stop_telegram_polling() -> None:
    global _polling_task

    async with _polling_lock:
        if _polling_task is None:
            return
        _polling_task.cancel()
        task = _polling_task
        _polling_task = None

    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("telegram_polling_stopped")


async def _poll_loop() -> None:
    global _polling_offset

    while True:
        settings = get_settings()
        client = TelegramClient(bot_token=settings.telegram_bot_token)
        updates = await asyncio.to_thread(
            client.get_updates,
            offset=_polling_offset,
            timeout_seconds=max(settings.telegram_poll_interval_seconds, 10),
        )
        if updates is None:
            await asyncio.sleep(settings.telegram_poll_interval_seconds)
            continue

        for update in updates:
            if update.update_id is not None:
                _polling_offset = update.update_id + 1
            if update.message is None or not update.message.text:
                continue
            await _process_message(update.message)

        await asyncio.sleep(settings.telegram_poll_interval_seconds)


async def _process_message(message) -> None:
    session_factory = get_session_factory()
    db = session_factory()
    try:
        result = handle_telegram_message(db=db, telegram_message=message)
        logger.info(
            "telegram_polling_message_processed",
            extra={
                "message_id": message.message_id,
                "chat_id": message.chat.id,
                "status": result.get("status"),
                "reason": result.get("reason"),
            },
        )
    finally:
        db.close()



