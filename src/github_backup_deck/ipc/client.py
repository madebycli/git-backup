from __future__ import annotations

import fcntl
import json
import os
import shutil
import signal
import socket
import struct
import subprocess
import time
from pathlib import Path
from typing import Any

from github_backup_deck import __version__
from github_backup_deck.config import runtime_dir, state_dir

_ACTIVE_JOB_STATES = {"running", "cancelling"}


def daemon_is_compatible(response: dict[str, Any] | None) -> bool:
    return bool(
        response
        and response.get("ok")
        and response.get("protocol") == 3
        and response.get("version") == __version__
    )


def daemon_job_is_active(response: dict[str, Any] | None) -> bool:
    job = response.get("job") if isinstance(response, dict) else None
    return isinstance(job, dict) and job.get("state") in _ACTIVE_JOB_STATES


class IpcClient:
    def __init__(self, socket_path: Path | None = None) -> None:
        self.socket_path = socket_path or runtime_dir() / "control-v3.sock"

    def _request_with_peer(
        self,
        payload: dict[str, Any],
        *,
        timeout: float = 5.0,
    ) -> tuple[dict[str, Any], int | None]:
        encoded = (json.dumps(payload, sort_keys=True) + "\n").encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(self.socket_path))
            peer_pid: int | None = None
            if hasattr(socket, "SO_PEERCRED"):
                try:
                    size = struct.calcsize("3i")
                    credentials = connection.getsockopt(socket.SOL_SOCKET, socket.SO_PEERCRED, size)
                    peer_pid, _uid, _gid = struct.unpack("3i", credentials)
                except OSError:
                    peer_pid = None
            connection.sendall(encoded)
            chunks: list[bytes] = []
            while True:
                chunk = connection.recv(65536)
                if not chunk:
                    break
                chunks.append(chunk)
                if b"\n" in chunk:
                    break
        lines = b"".join(chunks).decode().splitlines()
        if not lines:
            raise RuntimeError("Empty IPC response")
        response = json.loads(lines[0])
        if not isinstance(response, dict):
            raise RuntimeError("Invalid IPC response")
        return response, peer_pid

    def request(self, payload: dict[str, Any], *, timeout: float = 5.0) -> dict[str, Any]:
        response, _peer_pid = self._request_with_peer(payload, timeout=timeout)
        return response

    def _probe(self) -> tuple[dict[str, Any] | None, int | None]:
        try:
            return self._request_with_peer({"command": "ping"}, timeout=1.0)
        except (OSError, RuntimeError, json.JSONDecodeError):
            return None, None

    def ping(self) -> bool:
        response, _peer_pid = self._probe()
        return daemon_is_compatible(response)

    def _status(self) -> dict[str, Any] | None:
        try:
            return self.request({"command": "status", "after_sequence": 0}, timeout=1.5)
        except (OSError, RuntimeError, json.JSONDecodeError, ValueError):
            return None

    def _retire_stale_daemon(
        self,
        peer_pid: int | None,
        response: dict[str, Any] | None,
    ) -> None:
        candidate = peer_pid
        if candidate is None and isinstance(response, dict):
            raw_pid = response.get("pid")
            if isinstance(raw_pid, int):
                candidate = raw_pid
        if candidate is not None and candidate > 1 and candidate != os.getpid():
            try:
                os.kill(candidate, signal.SIGTERM)
            except ProcessLookupError:
                pass
            else:
                deadline = time.monotonic() + 3.0
                while time.monotonic() < deadline:
                    try:
                        os.kill(candidate, 0)
                    except ProcessLookupError:
                        break
                    time.sleep(0.05)
                else:
                    try:
                        os.kill(candidate, signal.SIGKILL)
                    except ProcessLookupError:
                        pass
        self.socket_path.unlink(missing_ok=True)

    def ensure_server(self, *, timeout: float = 10.0) -> None:
        response, _peer_pid = self._probe()
        if daemon_is_compatible(response):
            return

        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.socket_path.parent, 0o700)
        lock_path = self.socket_path.parent / "daemon-start.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            response, peer_pid = self._probe()
            if daemon_is_compatible(response):
                return

            if response is not None:
                status = self._status()
                if daemon_job_is_active(status):
                    # Never terminate a previous-version daemon in the middle of a
                    # backup. The UI may keep monitoring it. The next action that
                    # calls ensure_server() after completion will replace it.
                    return
                self._retire_stale_daemon(peer_pid, response)
            else:
                self.socket_path.unlink(missing_ok=True)

            executable = shutil.which("github-backup-deck-daemon")
            if executable is None:
                raise RuntimeError("github-backup-deck-daemon is not available")
            log_path = state_dir() / "daemon.log"
            log_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
            log_handle = log_path.open("ab", buffering=0)
            try:
                subprocess.Popen(
                    [executable, "--socket", str(self.socket_path)],
                    stdin=subprocess.DEVNULL,
                    stdout=log_handle,
                    stderr=log_handle,
                    close_fds=True,
                    start_new_session=True,
                )
            finally:
                log_handle.close()
            deadline = time.monotonic() + timeout
            while time.monotonic() < deadline:
                response, _peer_pid = self._probe()
                if daemon_is_compatible(response):
                    return
                time.sleep(0.1)
            raise RuntimeError(f"Backup daemon did not start; see {log_path}")
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
