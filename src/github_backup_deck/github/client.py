from __future__ import annotations

import json
import threading
from typing import Any
from urllib.parse import urlencode

from github_backup_deck.process import run_command


class GitHubClient:
    def api(
        self,
        endpoint: str,
        *,
        paginate: bool = False,
        timeout: float = 300.0,
        query: dict[str, str | int] | None = None,
        cancel_event: threading.Event | None = None,
    ) -> Any:
        if query:
            separator = "&" if "?" in endpoint else "?"
            endpoint = f"{endpoint}{separator}{urlencode(query)}"
        args = ["gh", "api"]
        if paginate:
            args.extend(["--paginate", "--slurp"])
        args.append(endpoint)
        result = run_command(args, timeout=timeout, cancel_event=cancel_event)
        try:
            return json.loads(result.stdout)
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"GitHub CLI returned invalid JSON for {endpoint}") from exc

    def paginated_items(
        self,
        endpoint: str,
        *,
        timeout: float = 300.0,
        cancel_event: threading.Event | None = None,
    ) -> list[dict[str, Any]]:
        payload = self.api(
            endpoint,
            paginate=True,
            timeout=timeout,
            cancel_event=cancel_event,
        )
        pages = payload if isinstance(payload, list) else []
        flattened: list[dict[str, Any]] = []
        for page in pages:
            if isinstance(page, list):
                flattened.extend(item for item in page if isinstance(item, dict))
            elif isinstance(page, dict):
                flattened.append(page)
        return flattened
