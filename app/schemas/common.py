from __future__ import annotations

from pydantic import BaseModel, ConfigDict


class GraphResourceIdentifiers(BaseModel):
    model_config = ConfigDict(extra="forbid")

    conversation_type: str
    team_id: str | None = None
    channel_id: str | None = None
    chat_id: str | None = None
    message_id: str
    reply_id: str | None = None

    @property
    def external_message_id(self) -> str:
        return self.reply_id or self.message_id

    @property
    def thread_id(self) -> str:
        return self.message_id

    @property
    def parent_message_id(self) -> str | None:
        if self.conversation_type == "channel":
            return self.message_id
        return None
