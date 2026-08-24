from __future__ import annotations

import threading
from pathlib import Path

from github_backup_deck.backup.git_auth import github_git_command
from github_backup_deck.backup.git_state import has_refs
from github_backup_deck.models import Repository
from github_backup_deck.process import run_command


class GitMirror:
    def sync(
        self,
        repository: Repository,
        workspace: Path,
        *,
        fetch_lfs: bool = True,
        cancel_event: threading.Event | None = None,
    ) -> Path:
        mirror = workspace / "mirrors" / f"{repository.full_name}.git"
        mirror.parent.mkdir(parents=True, exist_ok=True)
        if mirror.exists():
            run_command(
                ["git", "-C", str(mirror), "remote", "set-url", "origin", repository.clone_url],
                timeout=60,
                cancel_event=cancel_event,
            )
        else:
            run_command(
                github_git_command("clone", "--mirror", repository.clone_url, str(mirror)),
                timeout=3600,
                cancel_event=cancel_event,
            )
        run_command(
            [
                "git",
                "-C",
                str(mirror),
                "config",
                "--replace-all",
                "remote.origin.fetch",
                "+refs/*:refs/*",
            ],
            timeout=60,
            cancel_event=cancel_event,
        )
        run_command(
            github_git_command("-C", str(mirror), "remote", "update", "--prune"),
            timeout=3600,
            cancel_event=cancel_event,
        )
        if fetch_lfs and has_refs(mirror, cancel_event=cancel_event):
            run_command(
                github_git_command("-C", str(mirror), "lfs", "fetch", "--all"),
                timeout=7200,
                cancel_event=cancel_event,
            )
        return mirror
