from __future__ import annotations

import fcntl
import json
import os
import shutil
import socket
import subprocess
import time
from pathlib import Path
from typing import Any

from github_backup_deck.config import runtime_dir, state_dir


class IpcClient:
    def __init__(self, socket_path: Path | None = None) -> None:
        self.socket_path = socket_path or runtime_dir() / "control-v3.sock"

    def request(self, payload: dict[str, Any], *, timeout: float = 5.0) -> dict[str, Any]:
        encoded = (json.dumps(payload, sort_keys=True) + "\n").encode()
        with socket.socket(socket.AF_UNIX, socket.SOCK_STREAM) as connection:
            connection.settimeout(timeout)
            connection.connect(str(self.socket_path))
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
        return response

    def ping(self) -> bool:
        try:
            response = self.request({"command": "ping"}, timeout=1.0)
            return bool(response.get("ok") and response.get("protocol") == 3)
        except (OSError, RuntimeError, json.JSONDecodeError):
            return False

    def ensure_server(self, *, timeout: float = 10.0) -> None:
        if self.ping():
            return
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.socket_path.parent, 0o700)
        lock_path = self.socket_path.parent / "daemon-start.lock"
        descriptor = os.open(lock_path, os.O_CREAT | os.O_RDWR, 0o600)
        try:
            fcntl.flock(descriptor, fcntl.LOCK_EX)
            if self.ping():
                return
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
                if self.ping():
                    return
                time.sleep(0.1)
            raise RuntimeError(f"Backup daemon did not start; see {log_path}")
        finally:
            fcntl.flock(descriptor, fcntl.LOCK_UN)
            os.close(descriptor)
