from __future__ import annotations

import json
import os
import socketserver
from pathlib import Path
from typing import Any, Callable

from github_backup_deck.config import runtime_dir

RequestHandler = Callable[[dict[str, Any]], dict[str, Any]]


class _UnixRequestHandler(socketserver.StreamRequestHandler):
    def handle(self) -> None:
        raw = self.rfile.readline(1024 * 1024)
        try:
            payload = json.loads(raw.decode("utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("request must be an object")
            response = self.server.dispatch(payload)  # type: ignore[attr-defined]
        except Exception as exc:  # noqa: BLE001 - protocol boundary
            response = {"ok": False, "error": str(exc)}
        self.wfile.write((json.dumps(response, sort_keys=True) + "\n").encode("utf-8"))


class UnixIpcServer(socketserver.ThreadingUnixStreamServer):
    daemon_threads = True
    allow_reuse_address = True

    def __init__(self, handler: RequestHandler, socket_path: Path | None = None) -> None:
        self.socket_path = socket_path or runtime_dir() / "control.sock"
        self.socket_path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        os.chmod(self.socket_path.parent, 0o700)
        self.socket_path.unlink(missing_ok=True)
        self._handler = handler
        super().__init__(str(self.socket_path), _UnixRequestHandler)
        os.chmod(self.socket_path, 0o600)

    def dispatch(self, payload: dict[str, Any]) -> dict[str, Any]:
        return self._handler(payload)

    def server_close(self) -> None:
        super().server_close()
        self.socket_path.unlink(missing_ok=True)
