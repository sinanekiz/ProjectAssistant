from __future__ import annotations

from dataclasses import dataclass
from typing import Any
from urllib.parse import urlencode

import httpx

from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class OAuthTokenResult:
    success: bool
    access_token: str | None = None
    refresh_token: str | None = None
    expires_in: int | None = None
    scope: str | None = None
    token_type: str | None = None
    error: str | None = None
    raw: dict[str, Any] | None = None


def build_github_authorize_url(*, client_id: str, redirect_uri: str, state: str, scope: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "scope": scope,
        "state": state,
        "allow_signup": "false",
    }
    return "https://github.com/login/oauth/authorize?" + urlencode(params)


def exchange_github_code(*, client_id: str, client_secret: str, code: str, redirect_uri: str) -> OAuthTokenResult:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    try:
        response = httpx.post(
            "https://github.com/login/oauth/access_token",
            data=payload,
            headers={"Accept": "application/json"},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("github_oauth_exchange_failed", extra={"error": str(exc)})
        return OAuthTokenResult(success=False, error="GitHub token alinamadi.")

    if "access_token" not in data:
        return OAuthTokenResult(success=False, error=data.get("error_description") or data.get("error") or "GitHub token alinamadi.")

    return OAuthTokenResult(
        success=True,
        access_token=data.get("access_token"),
        token_type=data.get("token_type"),
        scope=data.get("scope"),
        raw=data,
    )


def build_google_authorize_url(*, client_id: str, redirect_uri: str, state: str, scope: str) -> str:
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "access_type": "offline",
        "prompt": "consent",
        "scope": scope,
        "include_granted_scopes": "true",
        "state": state,
    }
    return "https://accounts.google.com/o/oauth2/v2/auth?" + urlencode(params)


def exchange_google_code(*, client_id: str, client_secret: str, code: str, redirect_uri: str) -> OAuthTokenResult:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
        "grant_type": "authorization_code",
    }
    try:
        response = httpx.post("https://oauth2.googleapis.com/token", data=payload, timeout=20.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("google_oauth_exchange_failed", extra={"error": str(exc)})
        return OAuthTokenResult(success=False, error="Google token alinamadi.")

    if "access_token" not in data:
        return OAuthTokenResult(success=False, error=data.get("error_description") or data.get("error") or "Google token alinamadi.")

    return OAuthTokenResult(
        success=True,
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        expires_in=int(data.get("expires_in") or 0) if data.get("expires_in") else None,
        scope=data.get("scope"),
        token_type=data.get("token_type"),
        raw=data,
    )


def refresh_google_access_token(*, client_id: str, client_secret: str, refresh_token: str) -> OAuthTokenResult:
    payload = {
        "client_id": client_id,
        "client_secret": client_secret,
        "refresh_token": refresh_token,
        "grant_type": "refresh_token",
    }
    try:
        response = httpx.post("https://oauth2.googleapis.com/token", data=payload, timeout=20.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("google_oauth_refresh_failed", extra={"error": str(exc)})
        return OAuthTokenResult(success=False, error="Google token yenilenemedi.")

    if "access_token" not in data:
        return OAuthTokenResult(success=False, error=data.get("error_description") or data.get("error") or "Google token yenilenemedi.")

    return OAuthTokenResult(
        success=True,
        access_token=data.get("access_token"),
        expires_in=int(data.get("expires_in") or 0) if data.get("expires_in") else None,
        scope=data.get("scope"),
        token_type=data.get("token_type"),
        raw=data,
    )


def build_atlassian_authorize_url(*, client_id: str, redirect_uri: str, state: str, scope: str) -> str:
    params = {
        "audience": "api.atlassian.com",
        "client_id": client_id,
        "scope": scope,
        "redirect_uri": redirect_uri,
        "state": state,
        "response_type": "code",
        "prompt": "consent",
    }
    return "https://auth.atlassian.com/authorize?" + urlencode(params)


def exchange_atlassian_code(*, client_id: str, client_secret: str, code: str, redirect_uri: str) -> OAuthTokenResult:
    payload = {
        "grant_type": "authorization_code",
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "redirect_uri": redirect_uri,
    }
    try:
        response = httpx.post("https://auth.atlassian.com/oauth/token", json=payload, timeout=20.0)
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("atlassian_oauth_exchange_failed", extra={"error": str(exc)})
        return OAuthTokenResult(success=False, error="Atlassian token alinamadi.")

    if "access_token" not in data:
        return OAuthTokenResult(success=False, error=data.get("error_description") or data.get("error") or "Atlassian token alinamadi.")

    return OAuthTokenResult(
        success=True,
        access_token=data.get("access_token"),
        refresh_token=data.get("refresh_token"),
        expires_in=int(data.get("expires_in") or 0) if data.get("expires_in") else None,
        scope=data.get("scope"),
        token_type=data.get("token_type"),
        raw=data,
    )


def fetch_atlassian_resources(*, access_token: str) -> list[dict[str, Any]]:
    try:
        response = httpx.get(
            "https://api.atlassian.com/oauth/token/accessible-resources",
            headers={"Authorization": f"Bearer {access_token}"},
            timeout=20.0,
        )
        response.raise_for_status()
        data = response.json()
    except Exception as exc:  # pragma: no cover - network
        logger.warning("atlassian_resources_fetch_failed", extra={"error": str(exc)})
        return []

    if isinstance(data, list):
        return data
    return []
