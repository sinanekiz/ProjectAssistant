from __future__ import annotations

from dataclasses import dataclass
from urllib.parse import urlparse

from app.adapters.github_client import GithubClient
from app.logging import get_logger
from app.services.context_records import upsert_context_entry
from app.services.integration_utils import get_enabled_integration, get_integration_config

logger = get_logger(__name__)


@dataclass(slots=True)
class GithubContextResult:
    summary: str
    entries: int


def _infer_repo_from_base_url(base_url: str) -> str | None:
    normalized = base_url.strip()
    if not normalized:
        return None
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    parsed = urlparse(normalized)
    if parsed.netloc in ("github.com", "www.github.com"):
        parts = [part for part in parsed.path.split("/") if part]
        if len(parts) >= 2:
            return f"{parts[0]}/{parts[1]}"
    return None


def _normalize_base_url(base_url: str | None) -> str:
    if not base_url:
        return "https://api.github.com"
    normalized = base_url.strip()
    if not normalized:
        return "https://api.github.com"
    if "://" not in normalized:
        normalized = f"https://{normalized}"
    parsed = urlparse(normalized)
    if parsed.netloc in ("github.com", "www.github.com"):
        return "https://api.github.com"
    if "api.github.com" in parsed.netloc:
        return "https://api.github.com"
    return normalized.rstrip("/")


def refresh_github_context(db, *, project) -> GithubContextResult:
    integration = get_enabled_integration(project, "github")
    if integration is None:
        return GithubContextResult(summary="GitHub entegrasyonu bulunamadi.", entries=0)

    config = get_integration_config(integration)
    token = config.get("token") or config.get("access_token")
    repo = integration.external_id or config.get("repo") or config.get("repository")
    base_url = integration.base_url or config.get("base_url")
    if not repo and base_url:
        repo = _infer_repo_from_base_url(base_url)
        if repo:
            logger.info(
                "github_repo_inferred",
                extra={"taskName": None, "repo": repo, "base_url": base_url},
            )
    if not repo:
        return GithubContextResult(
            summary="GitHub repo bilgisi eksik. External ID olarak owner/repo girin.",
            entries=0,
        )

    base_url = _normalize_base_url(base_url)
    client = GithubClient(base_url=base_url, token=token)

    repo_summary = client.get_repo(repo)
    languages = client.list_languages(repo)
    commits = client.list_recent_commits(repo, limit=5)

    language_list = ", ".join(languages.keys()) if languages else repo_summary.language
    overview_lines = [
        f"Repo: {repo_summary.full_name}",
        f"Default branch: {repo_summary.default_branch}",
        f"Open issues: {repo_summary.open_issues}",
    ]
    if repo_summary.description:
        overview_lines.append(f"Description: {repo_summary.description}")
    if language_list:
        overview_lines.append(f"Languages: {language_list}")
    if repo_summary.html_url:
        overview_lines.append(f"URL: {repo_summary.html_url}")

    commit_lines: list[str] = []
    for item in commits:
        commit = item.get("commit", {})
        message = (commit.get("message") or "").split("\n")[0]
        author = (commit.get("author") or {}).get("name") or ""
        sha = item.get("sha") or ""
        if message:
            commit_lines.append(f"- {message} ({author}) {sha[:7]}")

    entries = 0
    _, created = upsert_context_entry(
        db,
        project=project,
        title="GitHub Repo Overview",
        section="github",
        content="\n".join(overview_lines),
        source_type="github",
        source_ref=f"github:{repo}:overview",
    )
    entries += 1 if created else 0

    if commit_lines:
        _, created = upsert_context_entry(
            db,
            project=project,
            title="Recent GitHub Commits",
            section="github",
            content="\n".join(commit_lines),
            source_type="github",
            source_ref=f"github:{repo}:commits",
        )
        entries += 1 if created else 0

    summary = f"GitHub context guncellendi ({repo})."
    return GithubContextResult(summary=summary, entries=entries)
