from __future__ import annotations

from dataclasses import dataclass
import re

from app.adapters.graph_client import GraphClient
from app.config import get_settings

_CHANNEL_RESOURCE_RE = re.compile(r"^/?teams/(?P<team_id>[^/]+)/channels/(?P<channel_id>[^/]+)/messages$", re.IGNORECASE)


@dataclass(slots=True)
class AvailableChannel:
    team_id: str
    team_name: str
    channel_id: str
    channel_name: str
    membership_type: str | None = None

    @property
    def value(self) -> str:
        return f"{self.team_id}||{self.channel_id}||{self.team_name}||{self.channel_name}"

    @property
    def label(self) -> str:
        if self.membership_type:
            return f"{self.team_name} / {self.channel_name} ({self.membership_type})"
        return f"{self.team_name} / {self.channel_name}"


@dataclass(slots=True)
class GraphSubscriptionView:
    subscription_id: str
    resource: str
    expiration: str | None
    team_id: str | None
    channel_id: str | None
    label: str


@dataclass(slots=True)
class GraphSubscriptionActionSummary:
    notice: str
    errors: list[str]


def load_graph_console_data() -> tuple[list[AvailableChannel], list[GraphSubscriptionView], list[str]]:
    settings = get_settings()
    errors: list[str] = []
    if not settings.microsoft_tenant_id or not settings.microsoft_client_id or not settings.microsoft_client_secret:
        return [], [], ["Microsoft Graph kimlik bilgileri eksik. Setup ekranindan tenant, client ve secret alanlarini doldur."]

    client = GraphClient.from_settings()
    channels = _load_available_channels(client, errors)
    subscriptions = _load_graph_subscriptions(client, channels, errors)
    return channels, subscriptions, errors


def subscribe_to_channels(target_values: list[str]) -> GraphSubscriptionActionSummary:
    settings = get_settings()
    if not target_values:
        return GraphSubscriptionActionSummary(notice="Abone olmak icin en az bir kanal secmelisin.", errors=[])
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
        parsed = parse_channel_target_value(target_value)
        if parsed is None:
            errors.append(f"Gecersiz kanal secimi: {target_value}")
            continue

        team_id, channel_id, team_name, channel_name = parsed
        resource = normalize_resource(f"/teams/{team_id}/channels/{channel_id}/messages")
        label = f"{team_name} / {channel_name}"
        if resource in existing_resources:
            skipped_labels.append(label)
            continue

        created = client.create_channel_message_subscription(
            team_id=team_id,
            channel_id=channel_id,
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
        parts.append(f"{len(created_labels)} kanal icin abonelik olusturuldu.")
    if skipped_labels:
        parts.append(f"{len(skipped_labels)} kanal zaten aboneli listesinde oldugu icin atlandi.")
    if not parts and errors:
        parts.append("Hic abonelik olusturulamadi.")
    if not parts:
        parts.append("Degisiklik yapilmadi.")

    return GraphSubscriptionActionSummary(notice=" ".join(parts), errors=errors)


def parse_channel_target_value(value: str) -> tuple[str, str, str, str] | None:
    parts = value.split("||", 3)
    if len(parts) != 4 or not parts[0] or not parts[1]:
        return None
    return parts[0], parts[1], parts[2], parts[3]


def normalize_resource(resource: str) -> str:
    return resource.strip().lstrip("/").lower()


def _load_available_channels(client: GraphClient, errors: list[str]) -> list[AvailableChannel]:
    teams = client.list_teams()
    if teams is None:
        errors.append("Teams listesi Graph'tan alinamadi. Uygulama izinlerini ve admin consent ayarlarini kontrol et.")
        return []

    channels: list[AvailableChannel] = []
    for team in teams:
        team_id = str(team.get("id") or "")
        if not team_id:
            continue
        team_name = str(team.get("displayName") or team_id)
        team_channels = client.list_channels(team_id=team_id)
        if team_channels is None:
            errors.append(f"{team_name} takiminin kanallari alinamadi.")
            continue
        for channel in team_channels:
            channel_id = str(channel.get("id") or "")
            if not channel_id:
                continue
            channels.append(
                AvailableChannel(
                    team_id=team_id,
                    team_name=team_name,
                    channel_id=channel_id,
                    channel_name=str(channel.get("displayName") or channel_id),
                    membership_type=channel.get("membershipType"),
                )
            )
    return channels


def _load_graph_subscriptions(
    client: GraphClient,
    channels: list[AvailableChannel],
    errors: list[str],
) -> list[GraphSubscriptionView]:
    subscription_payloads = client.list_subscriptions()
    if subscription_payloads is None:
        errors.append("Mevcut Graph abonelikleri alinamadi.")
        return []

    channel_labels = {
        (channel.team_id, channel.channel_id): channel.label
        for channel in channels
    }
    subscriptions: list[GraphSubscriptionView] = []
    for item in subscription_payloads:
        resource = str(item.get("resource") or "")
        match = _CHANNEL_RESOURCE_RE.match(resource)
        team_id = None
        channel_id = None
        label = resource or "Unknown resource"
        if match is not None:
            team_id = match.group("team_id")
            channel_id = match.group("channel_id")
            label = channel_labels.get((team_id, channel_id), f"{team_id} / {channel_id}")
        subscriptions.append(
            GraphSubscriptionView(
                subscription_id=str(item.get("id") or "-"),
                resource=resource,
                expiration=item.get("expirationDateTime"),
                team_id=team_id,
                channel_id=channel_id,
                label=label,
            )
        )
    subscriptions.sort(key=lambda item: (item.label or item.resource).lower())
    return subscriptions
