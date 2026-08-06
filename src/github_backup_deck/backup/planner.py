from __future__ import annotations

from pathlib import Path

from github_backup_deck.github.repositories import RepositoryService
from github_backup_deck.models import BackupOptions, BackupPlan
from github_backup_deck.storage.probe import probe_path


class BackupPlanner:
    def __init__(self, repositories: RepositoryService | None = None) -> None:
        self.repositories = repositories or RepositoryService()

    def create(self, destination: Path, options: BackupOptions) -> BackupPlan:
        probe = probe_path(destination)
        if not probe.ok:
            raise RuntimeError(probe.error or "Backup destination is not writable")
        repos = self.repositories.list_accessible(include_archived=options.include_archived)
        return BackupPlan(destination.resolve(), tuple(repos), options)
