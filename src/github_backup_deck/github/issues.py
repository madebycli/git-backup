from __future__ import annotations

from typing import Any

from github_backup_deck.github.client import GitHubClient


def fetch_issues(client: GitHubClient, full_name: str) -> list[dict[str, Any]]:
    items = client.paginated_items(f"/repos/{full_name}/issues?state=all&per_page=100")
    return [item for item in items if "pull_request" not in item]
