from __future__ import annotations

from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator, model_validator


class TeamsActor(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    name: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")

    @model_validator(mode="before")
    @classmethod
    def unwrap_user(cls, value: Any) -> Any:
        if isinstance(value, dict) and isinstance(value.get("user"), dict):
            nested_user = value["user"]
            return {
                **value,
                "id": value.get("id") or nested_user.get("id"),
                "name": value.get("name") or nested_user.get("name") or nested_user.get("displayName"),
                "displayName": value.get("displayName") or nested_user.get("displayName"),
            }
        return value

    @property
    def resolved_name(self) -> str | None:
        return self.name or self.display_name


class TeamsConversation(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    channel_id: str | None = Field(default=None, alias="channelId")
    channel_name: str | None = Field(default=None, alias="channelName")
    thread_id: str | None = Field(default=None, alias="threadId")


class IncomingTeamsWebhook(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    external_message_id: str = Field(validation_alias=AliasChoices("id", "messageId", "external_message_id"))
    text: str = Field(validation_alias=AliasChoices("text", "body", "message", "messageText"))
    sender: TeamsActor | None = Field(default=None, validation_alias=AliasChoices("from", "sender"))
    mentions: list[str] = Field(default_factory=list)
    channel_id: str | None = Field(default=None, validation_alias=AliasChoices("channelId", "channel_id"))
    channel_name: str | None = Field(default=None, validation_alias=AliasChoices("channelName", "channel_name"))
    thread_id: str | None = Field(default=None, validation_alias=AliasChoices("replyToId", "threadId", "thread_id"))
    conversation: TeamsConversation | None = None

    @field_validator("text", mode="before")
    @classmethod
    def normalize_text(cls, value: Any) -> str:
        if isinstance(value, str):
            return value
        if isinstance(value, dict):
            for key in ("content", "text", "plainText"):
                if value.get(key):
                    return str(value[key])
        raise TypeError("Message text must be a string or text-like object")

    @field_validator("mentions", mode="before")
    @classmethod
    def normalize_mentions(cls, value: Any) -> list[str]:
        if value is None:
            return []
        if isinstance(value, list):
            normalized: list[str] = []
            for item in value:
                if isinstance(item, str):
                    normalized.append(item)
                elif isinstance(item, dict):
                    for key in ("name", "displayName", "text"):
                        if item.get(key):
                            normalized.append(str(item[key]))
                            break
            return normalized
        return []

    @model_validator(mode="after")
    def backfill_from_conversation(self) -> "IncomingTeamsWebhook":
        if self.conversation:
            self.channel_id = self.channel_id or self.conversation.channel_id
            self.channel_name = self.channel_name or self.conversation.channel_name
            self.thread_id = self.thread_id or self.conversation.thread_id or self.conversation.id
        return self


class GraphNotificationResourceData(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    team_id: str | None = Field(default=None, alias="teamId")
    channel_id: str | None = Field(default=None, alias="channelId")
    channel_name: str | None = Field(default=None, alias="channelName")
    chat_id: str | None = Field(default=None, alias="chatId")
    reply_to_id: str | None = Field(default=None, alias="replyToId")


class GraphNotificationItem(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    subscription_id: str | None = Field(default=None, alias="subscriptionId")
    change_type: str | None = Field(default=None, alias="changeType")
    resource: str
    client_state: str | None = Field(default=None, alias="clientState")
    tenant_id: str | None = Field(default=None, alias="tenantId")
    resource_data: GraphNotificationResourceData | None = Field(default=None, alias="resourceData")


class GraphChangeNotificationPayload(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    value: list[GraphNotificationItem] = Field(default_factory=list)


class GraphMessageUser(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")


class GraphMessageApplication(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str | None = None
    display_name: str | None = Field(default=None, alias="displayName")


class GraphMessageFrom(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user: GraphMessageUser | None = None
    application: GraphMessageApplication | None = None

    @property
    def sender_id(self) -> str | None:
        if self.user and self.user.id:
            return self.user.id
        if self.application and self.application.id:
            return self.application.id
        return None

    @property
    def sender_name(self) -> str | None:
        if self.user and self.user.display_name:
            return self.user.display_name
        if self.application and self.application.display_name:
            return self.application.display_name
        return None


class GraphMessageBody(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    content_type: str | None = Field(default=None, alias="contentType")
    content: str | None = None


class GraphMentionedEntity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    user: GraphMessageUser | None = None
    application: GraphMessageApplication | None = None

    @property
    def display_name(self) -> str | None:
        if self.user and self.user.display_name:
            return self.user.display_name
        if self.application and self.application.display_name:
            return self.application.display_name
        return None


class GraphMessageMention(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    mentioned: GraphMentionedEntity | None = None
    mention_text: str | None = Field(default=None, alias="mentionText")


class GraphChannelIdentity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    team_id: str | None = Field(default=None, alias="teamId")
    channel_id: str | None = Field(default=None, alias="channelId")
    channel_display_name: str | None = Field(default=None, alias="channelDisplayName")


class GraphChatIdentity(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    chat_id: str | None = Field(default=None, alias="chatId")


class GraphChatMessage(BaseModel):
    model_config = ConfigDict(populate_by_name=True, extra="allow")

    id: str
    reply_to_id: str | None = Field(default=None, alias="replyToId")
    chat_id: str | None = Field(default=None, alias="chatId")
    from_actor: GraphMessageFrom | None = Field(default=None, validation_alias=AliasChoices("from", "sender"))
    body: GraphMessageBody | None = None
    mentions: list[GraphMessageMention] = Field(default_factory=list)
    channel_identity: GraphChannelIdentity | None = Field(default=None, alias="channelIdentity")
    chat_identity: GraphChatIdentity | None = Field(default=None, alias="chatIdentity")


class NormalizedTeamsMessage(BaseModel):
    model_config = ConfigDict(extra="forbid")

    external_message_id: str
    sender_name: str | None
    sender_id: str | None
    channel_id: str | None
    channel_name: str | None
    thread_id: str | None
    message_text: str
    mentions: list[str]
    raw_payload: dict[str, Any]
    conversation_type: str | None = None
    team_id: str | None = None
    chat_id: str | None = None
    parent_message_id: str | None = None
