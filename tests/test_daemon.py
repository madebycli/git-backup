from __future__ import annotations

import threading
import time
from pathlib import Path

from github_backup_deck import __version__
from github_backup_deck.daemon import DaemonHandler, JobManager
from github_backup_deck.events import EventSink, ProgressEvent
from github_backup_deck.models import BackupSummary, RepositoryResult, utc_now
from github_backup_deck.process import CommandCancelled


class SlowApplication:
    def backup(
        self,
        destination: Path | None,
        sink: EventSink,
        *,
        cancel_event: threading.Event | None = None,
    ) -> BackupSummary:
        sink(ProgressEvent("progress", "working", current=1, total=2))
        while cancel_event is not None and not cancel_event.is_set():
            time.sleep(0.01)
        raise CommandCancelled("cancelled")


class FastApplication:
    def backup(
        self,
        destination: Path | None,
        sink: EventSink,
        *,
        cancel_event: threading.Event | None = None,
    ) -> BackupSummary:
        sink(ProgressEvent("success", "done", current=1, total=1))
        now = utc_now()
        return BackupSummary(
            "job",
            now,
            now,
            str(destination),
            1,
            1,
            0,
            (RepositoryResult("owner/demo", "ok", "", "", "/backup/demo.zip"),),
            "/backup/run",
        )


def test_job_survives_client_detach_and_reports_completion(tmp_path: Path) -> None:
    notifications: list[tuple[str, str]] = []
    manager = JobManager(
        application_factory=FastApplication,  # type: ignore[arg-type]
        notifier=lambda title, message, **_kwargs: notifications.append((title, message)),
        status_path=tmp_path / "status.json",
    )
    assert manager.start(tmp_path / "backup")["ok"]
    deadline = time.monotonic() + 2
    while manager.status()["job"]["state"] == "running" and time.monotonic() < deadline:
        time.sleep(0.01)
    response = manager.status(0)
    assert response["job"]["state"] == "completed"
    assert response["events"]
    assert notifications


def test_job_can_be_cancelled(tmp_path: Path) -> None:
    manager = JobManager(
        application_factory=SlowApplication,  # type: ignore[arg-type]
        notifier=lambda *_args, **_kwargs: None,
        status_path=tmp_path / "status.json",
    )
    assert manager.start(tmp_path / "backup")["ok"]
    assert manager.cancel()["ok"]
    deadline = time.monotonic() + 2
    while (
        manager.status()["job"]["state"] in {"running", "cancelling"}
        and time.monotonic() < deadline
    ):
        time.sleep(0.01)
    assert manager.status()["job"]["state"] == "cancelled"


def test_daemon_ping_reports_runtime_version_and_pid(tmp_path: Path) -> None:
    manager = JobManager(
        application_factory=FastApplication,  # type: ignore[arg-type]
        notifier=lambda *_args, **_kwargs: None,
        status_path=tmp_path / "status.json",
    )
    response = DaemonHandler(manager)({"command": "ping"})
    assert response["ok"] is True
    assert response["protocol"] == 3
    assert response["version"] == __version__
    assert isinstance(response["pid"], int)
    assert response["pid"] > 1
