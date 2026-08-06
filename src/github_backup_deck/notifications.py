from __future__ import annotations

import shutil

from github_backup_deck.process import run_command


def notify_backup(title: str, message: str, *, urgency: str = "normal") -> None:
    executable = shutil.which("notify-send")
    if executable is None:
        return
    run_command(
        [
            executable,
            "--app-name=GitHub Backup Deck",
            f"--urgency={urgency}",
            "--icon=github-backup-deck",
            title,
            message,
        ],
        timeout=15,
        check=False,
    )
