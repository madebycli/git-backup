from __future__ import annotations

import argparse
import json
import os
import tempfile
import threading
from collections import deque
from collections.abc import Callable
from pathlib import Path
from typing import Any

from github_backup_deck.app import BackupApplication
from github_backup_deck.config import state_dir
from github_backup_deck.events import ProgressEvent
from github_backup_deck.ipc.server import UnixIpcServer
from github_backup_deck.models import BackupSummary, utc_now
from github_backup_deck.notifications import notify_backup
from github_backup_deck.process import CommandCancelled
from github_backup_deck.state import StateStore

ApplicationFactory = Callable[[], BackupApplication]
Notifier = Callable[..., None]


class JobManager:
    def __init__(
        self,
        *,
        application_factory: ApplicationFactory = BackupApplication,
        notifier: Notifier = notify_backup,
        status_path: Path | None = None,
        max_events: int = 2000,
    ) -> None:
        self.application_factory = application_factory
        self.notifier = notifier
        self.status_path = status_path or state_dir() / "job-status.json"
        self.events_path = self.status_path.with_name("job-events.jsonl")
        self.max_events = max_events
        self._lock = threading.RLock()
        self._cancel = threading.Event()
        self._worker: threading.Thread | None = None
        loaded_events = self._load_events()
        self._sequence = max(
            (int(event.get("sequence", 0)) for event in loaded_events),
            default=0,
        )
        self._events: deque[dict[str, Any]] = deque(loaded_events, maxlen=max_events)
        self._status: dict[str, Any] = self._load_status()
        self._sequence = max(self._sequence, int(self._status.get("last_sequence", 0) or 0))
        if self._status.get("state") in {"running", "cancelling"}:
            self._status.update(
                state="failed",
                message="Previous backup process ended unexpectedly",
                finished_at=utc_now(),
                error="daemon restarted while a backup was active",
            )
            self._persist()

    def start(self, destination: Path | None) -> dict[str, Any]:
        with self._lock:
            if self._status.get("state") in {"running", "cancelling"}:
                return {
                    "ok": False,
                    "error": "A backup is already running",
                    "job": self._snapshot(),
                }
            self._cancel = threading.Event()
            self._events.clear()
            self.events_path.unlink(missing_ok=True)
            self._status = {
                "state": "running",
                "job_id": os.urandom(8).hex(),
                "destination": str(destination) if destination is not None else None,
                "message": "Backup queued",
                "current": 0,
                "total": 0,
                "started_at": utc_now(),
                "finished_at": None,
                "summary": None,
                "error": None,
            }
            self._persist()
            self._worker = threading.Thread(
                target=self._run,
                args=(destination,),
                name="github-backup-job",
                daemon=True,
            )
            self._worker.start()
            return {"ok": True, "job": self._snapshot()}

    def cancel(self) -> dict[str, Any]:
        with self._lock:
            if self._status.get("state") not in {"running", "cancelling"}:
                return {
                    "ok": False,
                    "error": "No backup is running",
                    "job": self._snapshot(),
                }
            self._cancel.set()
            self._status["state"] = "cancelling"
            self._status["message"] = "Cancelling backup and cleaning temporary files"
            self._persist()
            return {"ok": True, "job": self._snapshot()}

    def status(self, after_sequence: int = 0) -> dict[str, Any]:
        with self._lock:
            events = [
                event.copy()
                for event in self._events
                if int(event["sequence"]) > after_sequence
            ]
            return {
                "ok": True,
                "job": self._snapshot(),
                "events": events,
                "last_sequence": self._sequence,
            }

    def _run(self, destination: Path | None) -> None:
        try:
            summary = self.application_factory().backup(
                destination,
                sink=self._record_event,
                cancel_event=self._cancel,
            )
        except CommandCancelled:
            with self._lock:
                self._status.update(
                    state="cancelled",
                    message="Backup cancelled; temporary staging was removed",
                    finished_at=utc_now(),
                    error=None,
                )
                self._persist()
            self._notify("Backup cancelled", "Temporary files were cleaned up.")
            return
        except Exception as exc:  # noqa: BLE001 - daemon job boundary
            with self._lock:
                self._status.update(
                    state="failed",
                    message="Backup failed",
                    finished_at=utc_now(),
                    error=str(exc),
                )
                self._persist()
            self._notify("Backup failed", str(exc), urgency="critical")
            return
        self._finish_summary(summary)

    def _finish_summary(self, summary: BackupSummary) -> None:
        complete = summary.repositories_failed == 0 and summary.snapshot_path is not None
        with self._lock:
            self._status.update(
                state="completed" if complete else "failed",
                message=(
                    "Backup completed and verified"
                    if complete
                    else "Backup was not published because verification failed"
                ),
                current=summary.repositories_total,
                total=summary.repositories_total,
                finished_at=summary.finished_at,
                summary=summary.to_dict(),
                error=None if complete else f"{summary.repositories_failed} repositories failed",
            )
            self._persist()
        if complete:
            self._notify(
                "GitHub backup completed",
                f"{summary.repositories_ok} repositories verified at {summary.snapshot_path}",
            )
        else:
            self._notify(
                "GitHub backup incomplete",
                "The selected destination was not replaced because verification failed.",
                urgency="critical",
            )

    def _record_event(self, event: ProgressEvent) -> None:
        with self._lock:
            self._sequence += 1
            payload = event.to_dict()
            payload["sequence"] = self._sequence
            self._events.append(payload)
            self._append_event(payload)
            self._status["message"] = event.message
            self._status["last_sequence"] = self._sequence
            if event.current is not None:
                self._status["current"] = event.current
            if event.total is not None:
                self._status["total"] = event.total
            self._persist()

    def _snapshot(self) -> dict[str, Any]:
        snapshot = self._status.copy()
        snapshot["last_sequence"] = self._sequence
        return snapshot

    def _load_status(self) -> dict[str, Any]:
        if not self.status_path.exists():
            return {
                "state": "idle",
                "job_id": None,
                "destination": None,
                "message": "No backup has been started",
                "current": 0,
                "total": 0,
                "started_at": None,
                "finished_at": None,
                "summary": StateStore().latest_summary(),
                "error": None,
            }
        try:
            payload = json.loads(self.status_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            return {
                "state": "failed",
                "message": "Could not read previous job status",
                "error": "invalid job status",
            }
        return (
            payload
            if isinstance(payload, dict)
            else {"state": "idle", "message": "No backup has been started"}
        )

    def _load_events(self) -> list[dict[str, Any]]:
        if not self.events_path.exists():
            return []
        events: list[dict[str, Any]] = []
        try:
            with self.events_path.open(encoding="utf-8") as handle:
                for line in handle:
                    value = json.loads(line)
                    if isinstance(value, dict):
                        events.append(value)
        except (OSError, json.JSONDecodeError):
            return []
        return events[-self.max_events :]

    def _append_event(self, payload: dict[str, Any]) -> None:
        self.events_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        with self.events_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(payload, sort_keys=True) + "\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(self.events_path, 0o600)

    def _persist(self) -> None:
        self.status_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        fd, name = tempfile.mkstemp(
            prefix=f".{self.status_path.name}.",
            dir=self.status_path.parent,
        )
        temporary = Path(name)
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                json.dump(self._status, handle, indent=2, sort_keys=True)
                handle.write("\n")
                handle.flush()
                os.fsync(handle.fileno())
            os.chmod(temporary, 0o600)
            os.replace(temporary, self.status_path)
        finally:
            temporary.unlink(missing_ok=True)

    def _notify(self, title: str, message: str, *, urgency: str = "normal") -> None:
        try:
            self.notifier(title, message, urgency=urgency)
        except Exception:
            return


class DaemonHandler:
    def __init__(self, jobs: JobManager | None = None) -> None:
        self.jobs = jobs or JobManager()
        self.state = StateStore()

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        if command == "ping":
            return {"ok": True, "status": "ready", "protocol": 3}
        if command == "status":
            after = int(request.get("after_sequence", 0))
            response = self.jobs.status(after)
            response["latest_summary"] = self.state.latest_summary()
            return response
        if command == "start_backup":
            raw_destination = request.get("destination")
            destination = Path(str(raw_destination)).expanduser() if raw_destination else None
            return self.jobs.start(destination)
        if command == "cancel_backup":
            return self.jobs.cancel()
        return {"ok": False, "error": f"Unknown command: {command}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub Backup Deck background daemon")
    parser.add_argument("--socket", type=Path, help="Override Unix socket path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with UnixIpcServer(DaemonHandler(), args.socket) as server:
        try:
            server.serve_forever(poll_interval=0.25)
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
