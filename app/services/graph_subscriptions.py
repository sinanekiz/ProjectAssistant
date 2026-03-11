from __future__ import annotations

from dataclasses import dataclass
import re

from app.adapters.graph_client import GraphClient
from app.config import get_settings

_CHAT_RESOURCE_RE = re.compile(r"^/?chats/(?P<chat_id>[^/]+)/messages$", re.IGNORECASE)
_CHANNEL_RESOURCE_RE = re.compile(r"^/?teams/(?P<team_id>[^/]+)/channels/(?P<channel_id>[^/]+)/messages$", re.IGNORECASE)


@dataclass(slots=True)
class GraphSubscriptionTarget:
    target_type: str
    target_id: str
    label: str
    value: str
    chat_id: str | None = None
    chat_type: str | None = None


@dataclass(slots=True)
class GraphSubscriptionView:
    subscription_id: str
    resource: str
    expiration: str | None
    target_type: str
    target_id: str | None
    label: str


@dataclass(slots=True)
class GraphSubscriptionActionSummary:
    notice: str
    errors: list[str]


def load_graph_console_data() -> tuple[list[GraphSubscriptionTarget], list[GraphSubscriptionView], list[str]]:
    settings = get_settings()
    errors: list[str] = []
    if not settings.microsoft_tenant_id or not settings.microsoft_client_id or not settings.microsoft_client_secret:
        return [], [], ["Microsoft Graph kimlik bilgileri eksik. Setup ekranindan tenant, client ve secret alanlarini doldur."]
    if not settings.microsoft_user_id:
        return [], [], ["MICROSOFT_USER_ID ayari eksik. Kendi kullanici object id veya UPN degerini setup ekranina gir."]

    client = GraphClient.from_settings()
    targets = _load_user_chats(client, settings.microsoft_user_id, errors)
    subscriptions = _load_graph_subscriptions(client, targets, errors)
    return targets, subscriptions, errors


def subscribe_to_targets(target_values: list[str]) -> GraphSubscriptionActionSummary:
    settings = get_settings()
    if not target_values:
        return GraphSubscriptionActionSummary(notice="Abone olmak icin en az bir chat secmelisin.", errors=[])
    if not settings.public_webhook_base_url:
        return GraphSubscriptionActionSummary(notice="", errors=["PUBLIC_WEBHOOK_BASE_URL ayari eksik. Render URL'ini setup veya environment alanina gir."])

    client = GraphClient.from_settings()
    notification_url = settings.public_webhook_base_url.rstrip("/") + "/webhooks/graph"
    existing_subscriptions = client.list_subscriptions() or []
    existing_resources = {normalize_resource(item.get("resource", "")) for item in existing_subscriptions}

    created_labels: list[str] = []
    skipped_labels: list[str] = []
    errors: list[str] = []

    for target_value in target_values:
        parsed = parse_target_value(target_value)
        if parsed is None:
            errors.append(f"Gecersiz hedef secimi: {target_value}")
            continue

        target_type, target_id, label = parsed
        if target_type != "chat":
            errors.append(f"Desteklenmeyen hedef tipi: {target_type}")
            continue

        resource = normalize_resource(f"/chats/{target_id}/messages")
        if resource in existing_resources:
            skipped_labels.append(label)
            continue

        created = client.create_chat_message_subscription(
            chat_id=target_id,
            notification_url=notification_url,
            client_state=settings.graph_webhook_client_state,
        )
        if created is None:
            errors.append(f"Abonelik olusturulamadi: {label}")
            continue

        existing_resources.add(resource)
        created_labels.append(label)

    parts: list[str] = []
    if created_labels:
        parts.append(f"{len(created_labels)} chat icin abonelik olusturuldu.")
    if skipped_labels:
        parts.append(f"{len(skipped_labels)} chat zaten aboneli listesinde oldugu icin atlandi.")
    if not parts and errors:
        parts.append("Hic abonelik olusturulamadi.")
    if not parts:
        parts.append("Degisiklik yapilmadi.")

    return GraphSubscriptionActionSummary(notice=" ".join(parts), errors=errors)


def parse_target_value(value: str) -> tuple[str, str, str] | None:
    parts = value.split("||", 2)
    if len(parts) != 3 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1], parts[2]


def normalize_resource(resource: str) -> str:
    return resource.strip().lstrip("/").lower()


def _load_user_chats(client: GraphClient, user_id: str, errors: list[str]) -> list[GraphSubscriptionTarget]:
    chats = client.list_user_chats(user_id=user_id)
    if chats is None:
        errors.append("Kullanici chat listesi Graph'tan alinamadi. MICROSOFT_USER_ID, Chat.ReadBasic.All ve admin consent ayarlarini kontrol et.")
        return []

    targets: list[GraphSubscriptionTarget] = []
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            continue
        chat_type = str(chat.get("chatType") or "unknown")
        topic = str(chat.get("topic") or "").strip()
        member_label = _build_chat_member_label(client, chat_id, chat_type)
        if topic:
            label_text = topic
        elif member_label:
            label_text = member_label
        else:
            label_text = chat_id

        chat_prefix = {
            "oneOnOne": "Kisi",
            "group": "Grup",
            "meeting": "Toplanti",
        }.get(chat_type, "Chat")
        label = f"{chat_prefix} / {label_text}"
        targets.append(
            GraphSubscriptionTarget(
                target_type="chat",
                target_id=chat_id,
                label=label,
                value=f"chat||{chat_id}||{label}",
                chat_id=chat_id,
                chat_type=chat_type,
            )
        )
    targets.sort(key=lambda item: item.label.lower())
    return targets


def _build_chat_member_label(client: GraphClient, chat_id: str, chat_type: str) -> str:
    members = client.list_chat_members(chat_id=chat_id)
    if not members:
        return ""

    names: list[str] = []
    for member in members:
        display_name = str(member.get("displayName") or member.get("email") or member.get("userId") or "").strip()
        if display_name:
            names.append(display_name)
    if not names:
        return ""
    if chat_type == "oneOnOne" and len(names) >= 2:
        return " - ".join(names[:2])
    return ", ".join(names[:4])


def _load_graph_subscriptions(
    client: GraphClient,
    targets: list[GraphSubscriptionTarget],
    errors: list[str],
) -> list[GraphSubscriptionView]:
    subscription_payloads = client.list_subscriptions()
    if subscription_payloads is None:
        errors.append("Mevcut Graph abonelikleri alinamadi.")
        return []

    chat_labels = {
        target.chat_id: target.label
        for target in targets
        if target.target_type == "chat"
    }

    subscriptions: list[GraphSubscriptionView] = []
    for item in subscription_payloads:
        resource = str(item.get("resource") or "")
        label = resource or "Unknown resource"
        target_type = "unknown"
        target_id = None

        chat_match = _CHAT_RESOURCE_RE.match(resource)
        if chat_match is not None:
            chat_id = chat_match.group("chat_id")
            label = chat_labels.get(chat_id, f"Chat / {chat_id}")
            target_type = "chat"
            target_id = chat_id
        else:
            channel_match = _CHANNEL_RESOURCE_RE.match(resource)
            if channel_match is not None:
                target_type = "channel"
                target_id = f"{channel_match.group('team_id')}:{channel_match.group('channel_id')}"
                label = f"Kanal / {channel_match.group('team_id')} / {channel_match.group('channel_id')}"

        subscriptions.append(
            GraphSubscriptionView(
                subscription_id=str(item.get("id") or "-"),
                resource=resource,
                expiration=item.get("expirationDateTime"),
                target_type=target_type,
                target_id=target_id,
                label=label,
            )
        )
    subscriptions.sort(key=lambda item: (item.label or item.resource).lower())
    return subscriptions
