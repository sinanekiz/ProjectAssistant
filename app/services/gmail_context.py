from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone

from app.adapters.gmail_client import GmailClient
from app.config import get_settings
from app.logging import get_logger
from app.services.context_records import upsert_context_entry
from app.services.integration_utils import get_enabled_integration, get_integration_config
from app.services.oauth_integrations import refresh_google_access_token

logger = get_logger(__name__)


@dataclass(slots=True)
class GmailContextResult:
    summary: str
    entries: int


def _parse_expires_at(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed


def refresh_gmail_context(db, *, project) -> GmailContextResult:
    integration = get_enabled_integration(project, "gmail")
    if integration is None:
        return GmailContextResult(summary="Gmail entegrasyonu bulunamadi.", entries=0)

    config = get_integration_config(integration)
    access_token = config.get("access_token") or config.get("token")
    refresh_token = config.get("refresh_token")
    expires_at = _parse_expires_at(config.get("expires_at"))
    user_id = config.get("user_id", "me")
    query = config.get("query", "")
    max_results = int(config.get("max_results", 10))

    if access_token and expires_at and datetime.now(timezone.utc) >= expires_at:
        access_token = None

    if not access_token and refresh_token:
        settings = get_settings()
        if settings.google_client_id and settings.google_client_secret:
            token_result = refresh_google_access_token(
                client_id=settings.google_client_id,
                client_secret=settings.google_client_secret,
                refresh_token=refresh_token,
            )
            if token_result.success and token_result.access_token:
                access_token = token_result.access_token
                config_updates = {"access_token": access_token}
                if token_result.expires_in:
                    expires_at = datetime.now(timezone.utc) + timedelta(seconds=token_result.expires_in)
                    config_updates["expires_at"] = expires_at.isoformat()
                integration.config_json = {**config, **config_updates}
                db.add(integration)
                db.commit()
            else:
                logger.warning("gmail_refresh_failed", extra={"error": token_result.error})

    if not access_token:
        return GmailContextResult(summary="Gmail access token eksik.", entries=0)

    client = GmailClient(access_token=access_token)
    message_ids = client.list_messages(user_id=user_id, query=query, max_results=max_results)

    metadata_lines: list[str] = []
    for message_id in message_ids[:10]:
        metadata = client.get_message_metadata(user_id=user_id, message_id=message_id)
        if metadata.subject or metadata.sender:
            metadata_lines.append(
                f"- From: {metadata.sender} | Subject: {metadata.subject} | Date: {metadata.date}"
            )

    if not metadata_lines:
        summary = "Gmail mesajlari bulunamadi veya metadata cekilemedi."
        return GmailContextResult(summary=summary, entries=0)

    _, created = upsert_context_entry(
        db,
        project=project,
        title="Gmail Recent Subjects",
        section="gmail",
        content="\n".join(metadata_lines),
        source_type="gmail",
        source_ref=f"gmail:{user_id}:recent",
    )

    summary = "Gmail context guncellendi."
    return GmailContextResult(summary=summary, entries=1 if created else 0)
