from __future__ import annotations

from pathlib import Path

from github_backup_deck.backup.planner import BackupPlanner
from github_backup_deck.backup.runner import BackupRunner
from github_backup_deck.config import ConfigStore
from github_backup_deck.events import EventSink, null_sink
from github_backup_deck.models import BackupSummary


class BackupApplication:
    def __init__(
        self,
        config: ConfigStore | None = None,
        planner: BackupPlanner | None = None,
        runner: BackupRunner | None = None,
    ) -> None:
        self.config_store = config or ConfigStore()
        self.planner = planner or BackupPlanner()
        self.runner = runner or BackupRunner()

    def backup(self, destination: Path | None = None, sink: EventSink = null_sink) -> BackupSummary:
        config = self.config_store.load()
        target = destination.expanduser() if destination else config.backup_path
        plan = self.planner.create(target, config.options)
        return self.runner.run(plan, sink)
