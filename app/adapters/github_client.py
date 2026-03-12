from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import httpx

from app.logging import get_logger

logger = get_logger(__name__)


@dataclass(slots=True)
class GithubRepoSummary:
    full_name: str
    description: str
    default_branch: str
    open_issues: int
    language: str
    html_url: str


class GithubClient:
    def __init__(self, *, base_url: str = "https://api.github.com", token: str | None = None) -> None:
        self.base_url = base_url.rstrip("/")
        self.token = token

    def _headers(self) -> dict[str, str]:
        headers = {
            "Accept": "application/vnd.github+json",
            "User-Agent": "ProjectAssistant",
        }
        if self.token:
            headers["Authorization"] = f"Bearer {self.token}"
        return headers

    def get_repo(self, full_name: str) -> GithubRepoSummary:
        data = self._get_json(f"/repos/{full_name}")
        return GithubRepoSummary(
            full_name=data.get("full_name", full_name),
            description=data.get("description") or "",
            default_branch=data.get("default_branch") or "main",
            open_issues=int(data.get("open_issues_count") or 0),
            language=data.get("language") or "",
            html_url=data.get("html_url") or "",
        )

    def list_languages(self, full_name: str) -> dict[str, int]:
        return self._get_json(f"/repos/{full_name}/languages")

    def list_recent_commits(self, full_name: str, limit: int = 5) -> list[dict[str, Any]]:
        data = self._get_json(f"/repos/{full_name}/commits", params={"per_page": str(limit)})
        if isinstance(data, list):
            return data
        return []

    def _get_json(self, path: str, params: dict[str, str] | None = None) -> Any:
        url = f"{self.base_url}{path}"
        with httpx.Client(timeout=20.0) as client:
            response = client.get(url, headers=self._headers(), params=params)
        response.raise_for_status()
        return response.json()
