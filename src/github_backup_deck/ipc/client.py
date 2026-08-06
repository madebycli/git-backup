from __future__ import annotations

import json
import socket
from pathlib import Path
from typing import Any

from github_backup_deck.config import runtime_dir


class IpcClient:
    def __init__(self, socket_path: Path | None = None) -> None:
        self.socket_path = socket_path or runtime_dir() / "control.sock"

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
        response = json.loads(b"".join(chunks).decode().splitlines()[0])
        if not isinstance(response, dict):
            raise RuntimeError("Invalid IPC response")
        return response
