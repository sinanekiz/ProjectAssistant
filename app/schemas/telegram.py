from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, ConfigDict


ApprovalAction = Literal["approve", "reject", "revise", "details"]


class TelegramChat(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: int | str
    type: str | None = None


class TelegramMessage(BaseModel):
    model_config = ConfigDict(extra="ignore")

    message_id: int
    chat: TelegramChat
    text: str | None = None
    reply_to_message: TelegramMessage | None = None


class TelegramCallbackQuery(BaseModel):
    model_config = ConfigDict(extra="ignore")

    id: str
    data: str | None = None
    message: TelegramMessage | None = None


class TelegramWebhookUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")

    update_id: int | None = None
    callback_query: TelegramCallbackQuery | None = None
    message: TelegramMessage | None = None


class TelegramSendMessageResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    result: TelegramMessage | None = None
    description: str | None = None


class TelegramGenericResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    description: str | None = None


class TelegramGetUpdatesResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ok: bool
    result: list[TelegramWebhookUpdate] = []
    description: str | None = None


class ParsedApprovalCallback(BaseModel):
    action: ApprovalAction
    triage_result_id: int


TelegramMessage.model_rebuild()
