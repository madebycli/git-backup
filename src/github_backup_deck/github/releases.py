from __future__ import annotations

import threading
from typing import Any

from github_backup_deck.github.client import GitHubClient


def fetch_releases(
    client: GitHubClient,
    full_name: str,
    *,
    cancel_event: threading.Event | None = None,
) -> list[dict[str, Any]]:
    return client.paginated_items(
        f"/repos/{full_name}/releases?per_page=100",
        cancel_event=cancel_event,
    )
