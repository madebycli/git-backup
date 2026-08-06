from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path
from typing import Any, Iterable

from github_backup_deck.github.client import GitHubClient
from github_backup_deck.github.issues import fetch_issues
from github_backup_deck.github.pulls import fetch_pulls
from github_backup_deck.github.releases import fetch_releases
from github_backup_deck.models import BackupOptions, Repository


class MetadataWriter:
    def __init__(self, client: GitHubClient | None = None) -> None:
        self.client = client or GitHubClient()

    def write(
        self, repository: Repository, destination: Path, options: BackupOptions
    ) -> Path:
        metadata_dir = destination / "metadata" / repository.full_name
        metadata_dir.mkdir(parents=True, exist_ok=True)
        _atomic_json(metadata_dir / "repository.json", repository.to_dict())
        if options.include_issues:
            _atomic_jsonl(
                metadata_dir / "issues.jsonl",
                fetch_issues(self.client, repository.full_name),
            )
        if options.include_pull_requests:
            _atomic_jsonl(
                metadata_dir / "pulls.jsonl",
                fetch_pulls(self.client, repository.full_name),
            )
        if options.include_releases:
            _atomic_jsonl(
                metadata_dir / "releases.jsonl",
                fetch_releases(self.client, repository.full_name),
            )
        if options.include_action_artifacts:
            _atomic_json(
                metadata_dir / "action-artifacts.json",
                {
                    "status": "not-downloaded",
                    "reason": "Action artifact download requires an explicit retention policy",
                },
            )
        return metadata_dir


def _atomic_json(path: Path, payload: Any) -> None:
    _atomic_text(path, json.dumps(payload, indent=2, sort_keys=True) + "\n")


def _atomic_jsonl(path: Path, items: Iterable[dict[str, Any]]) -> None:
    text = "".join(json.dumps(item, sort_keys=True) + "\n" for item in items)
    _atomic_text(path, text)


def _atomic_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
