from __future__ import annotations

import sys
import threading
import time
from pathlib import Path

import pytest

from github_backup_deck.process import CommandCancelled, run_command


def test_command_can_be_cancelled() -> None:
    event = threading.Event()
    threading.Timer(0.1, event.set).start()
    started = time.monotonic()
    with pytest.raises(CommandCancelled):
        run_command(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            timeout=60,
            cancel_event=event,
        )
    assert time.monotonic() - started < 3


def test_git_process_receives_runtime_github_helper(tmp_path: Path) -> None:
    home = tmp_path / "home"
    home.mkdir()
    result = run_command(
        ["git", "config", "--get-all", "credential.https://github.com.helper"],
        env={"HOME": str(home)},
        check=False,
    )

    assert result.returncode == 0
    assert result.stdout.splitlines()[-1] == "!gh auth git-credential"
