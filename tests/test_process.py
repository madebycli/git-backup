from __future__ import annotations

import sys
import threading
import time

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
