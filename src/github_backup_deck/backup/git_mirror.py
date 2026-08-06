from __future__ import annotations

from pathlib import Path

from github_backup_deck.models import Repository
from github_backup_deck.process import run_command


class GitMirror:
    def sync(self, repository: Repository, destination: Path, *, fetch_lfs: bool = True) -> Path:
        mirror = destination / "repositories" / f"{repository.full_name}.git"
        mirror.parent.mkdir(parents=True, exist_ok=True)
        if mirror.exists():
            run_command(
                ["git", "-C", str(mirror), "remote", "set-url", "origin", repository.clone_url],
                timeout=60,
            )
            run_command(
                ["git", "-C", str(mirror), "remote", "update", "--prune"],
                timeout=1800,
            )
        else:
            run_command(
                ["git", "clone", "--mirror", repository.clone_url, str(mirror)],
                timeout=1800,
            )
        if fetch_lfs:
            run_command(
                ["git", "-C", str(mirror), "lfs", "fetch", "--all"],
                timeout=3600,
                check=False,
            )
        run_command(["git", "-C", str(mirror), "fsck", "--full"], timeout=1800)
        return mirror
