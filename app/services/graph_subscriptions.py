from __future__ import annotations

from dataclasses import dataclass
import re

from app.adapters.graph_client import GraphClient
from app.config import get_settings
from app.services.app_settings import read_chat_labels, write_chat_labels

_CHAT_RESOURCE_RE = re.compile(r"^/?chats/(?P<chat_id>[^/]+)/messages$", re.IGNORECASE)
_CHAT_LINK_RE = re.compile(r"/l/chat/(?P<chat_id>19:[^/?]+)", re.IGNORECASE)
_RAW_CHAT_ID_RE = re.compile(r"^(19:[A-Za-z0-9._=-]+@thread\.v2)$", re.IGNORECASE)


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


def load_teams_settings_data(*, fetch_targets: bool = False) -> tuple[list[GraphSubscriptionTarget], list[GraphSubscriptionView], list[str]]:
    settings = get_settings()
    errors: list[str] = []
    if not settings.microsoft_tenant_id or not settings.microsoft_client_id or not settings.microsoft_client_secret:
        return [], [], ["Microsoft Graph kimlik bilgileri eksik. Teams ayarlari ekranindan tenant, client ve secret alanlarini doldur."]

    client = GraphClient.from_settings()
    chat_labels = read_chat_labels(settings.database_url)
    targets: list[GraphSubscriptionTarget] = []
    if fetch_targets:
        if not settings.microsoft_delegated_connected:
            errors.append("Chat listesini cekebilmek ve senin hesabin olarak mesaj gonderebilmek icin once Microsoft hesabini bagla.")
        else:
            targets = _load_user_chats(client, chat_labels, errors)

    subscriptions = _load_graph_subscriptions(client, chat_labels, errors)
    return targets, subscriptions, errors


def subscribe_to_targets(target_values: list[str]) -> GraphSubscriptionActionSummary:
    settings = get_settings()
    if not target_values:
        return GraphSubscriptionActionSummary(notice="Abone olmak icin en az bir chat secmelisin.", errors=[])
    if not settings.public_webhook_base_url:
        return GraphSubscriptionActionSummary(notice="", errors=["PUBLIC_WEBHOOK_BASE_URL ayari eksik. Render URL'ini genel ayarlar ekranina gir."])

    client = GraphClient.from_settings()
    notification_url = settings.public_webhook_base_url.rstrip("/") + "/webhooks/graph"
    existing_subscriptions = client.list_subscriptions() or []
    existing_resources = {normalize_resource(item.get("resource", "")) for item in existing_subscriptions}
    chat_labels_to_save: dict[str, str] = {}

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
        chat_labels_to_save[target_id] = label

    if chat_labels_to_save:
        write_chat_labels(settings.database_url, chat_labels_to_save)

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


def save_subscription_labels(label_updates: dict[str, str]) -> GraphSubscriptionActionSummary:
    settings = get_settings()
    cleaned = {chat_id: label.strip() for chat_id, label in label_updates.items() if chat_id.strip() and label.strip()}
    if not cleaned:
        return GraphSubscriptionActionSummary(notice="Kaydedilecek label degisikligi yok.", errors=[])

    write_chat_labels(settings.database_url, cleaned)
    return GraphSubscriptionActionSummary(notice=f"{len(cleaned)} chat label guncellendi.", errors=[])


def build_manual_chat_target(chat_reference: str, label: str = "") -> tuple[GraphSubscriptionTarget | None, str | None]:
    normalized = chat_reference.strip()
    if not normalized:
        return None, "Chat linki veya chat id bos olamaz."

    chat_id = extract_chat_id(normalized)
    if chat_id is None:
        return None, "Chat linkinden veya girdigin degerden gecerli bir chat id ayiklanamadi."

    final_label = label.strip() or f"Chat / {chat_id}"
    return (
        GraphSubscriptionTarget(
            target_type="chat",
            target_id=chat_id,
            label=final_label,
            value=f"chat||{chat_id}||{final_label}",
            chat_id=chat_id,
        ),
        None,
    )


def parse_target_value(value: str) -> tuple[str, str, str] | None:
    parts = value.split("||", 2)
    if len(parts) != 3 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1], parts[2]


def normalize_resource(resource: str) -> str:
    return resource.strip().lstrip("/").lower()


def extract_chat_id(value: str) -> str | None:
    normalized = value.strip()

    raw_match = _RAW_CHAT_ID_RE.match(normalized)
    if raw_match is not None:
        return raw_match.group(1)

    link_match = _CHAT_LINK_RE.search(normalized)
    if link_match is not None:
        return link_match.group("chat_id")

    return None


def _load_user_chats(client: GraphClient, chat_labels: dict[str, str], errors: list[str]) -> list[GraphSubscriptionTarget]:
    chats = client.list_my_chats()
    if chats is None:
        errors.append("Kullanici chat listesi Graph'tan alinamadi. Teams web linki ile manuel chat ekleyebilirsin.")
        return []

    targets: list[GraphSubscriptionTarget] = []
    for chat in chats:
        chat_id = str(chat.get("id") or "")
        if not chat_id:
            continue
        chat_type = str(chat.get("chatType") or "unknown")
        topic = str(chat.get("topic") or "").strip()
        member_label = _build_chat_member_label(client, chat_id, chat_type)
        label_text = chat_labels.get(chat_id) or topic or member_label or chat_id

        chat_prefix = {
            "oneOnOne": "Kisi",
            "group": "Grup",
            "meeting": "Toplanti",
        }.get(chat_type, "Chat")
        label = label_text if label_text.startswith(("Kisi /", "Grup /", "Toplanti /", "Chat /")) else f"{chat_prefix} / {label_text}"
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
    members = client.list_chat_members(chat_id=chat_id, access_mode="delegated")
    if not members:
        return ""

    names: list[str] = []
    for member in members:
        display_name = _extract_member_display_name(member)
        if display_name and display_name not in names:
            names.append(display_name)
    if not names:
        return ""
    if chat_type == "oneOnOne" and len(names) >= 2:
        return " - ".join(names[:2])
    return ", ".join(names[:4])


def _extract_member_display_name(member: dict[str, object]) -> str:
    direct_keys = ("displayName", "email", "userId")
    for key in direct_keys:
        value = member.get(key)
        if value:
            return str(value).strip()

    user_value = member.get("user")
    if isinstance(user_value, dict):
        for key in ("displayName", "userPrincipalName", "email", "id"):
            value = user_value.get(key)
            if value:
                return str(value).strip()

    additional = member.get("additionalData")
    if isinstance(additional, dict):
        for key in ("displayName", "userPrincipalName", "email"):
            value = additional.get(key)
            if value:
                return str(value).strip()

    return ""


def _load_graph_subscriptions(
    client: GraphClient,
    chat_labels: dict[str, str],
    errors: list[str],
) -> list[GraphSubscriptionView]:
    subscription_payloads = client.list_subscriptions()
    if subscription_payloads is None:
        errors.append("Mevcut Graph abonelikleri alinamadi.")
        return []

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
