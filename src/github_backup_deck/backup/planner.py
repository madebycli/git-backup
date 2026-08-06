from __future__ import annotations

import threading
from pathlib import Path

from github_backup_deck.github.repositories import RepositoryService
from github_backup_deck.models import BackupOptions, BackupPlan
from github_backup_deck.storage.probe import probe_path


class BackupPlanner:
    def __init__(self, repositories: RepositoryService | None = None) -> None:
        self.repositories = repositories or RepositoryService()

    def create(
        self,
        destination: Path,
        options: BackupOptions,
        *,
        cancel_event: threading.Event | None = None,
    ) -> BackupPlan:
        target = destination.expanduser().resolve()
        probe_target = target if target.exists() else target.parent
        probe = probe_path(probe_target)
        if not probe.ok:
            raise RuntimeError(probe.error or "Backup destination parent is not writable")
        repos = self.repositories.list_accessible(
            include_archived=options.include_archived,
            cancel_event=cancel_event,
        )
        return BackupPlan(target, tuple(repos), options)
