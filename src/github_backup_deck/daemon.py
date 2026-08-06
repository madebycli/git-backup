from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any

from github_backup_deck.app import BackupApplication
from github_backup_deck.ipc.server import UnixIpcServer
from github_backup_deck.state import StateStore


class DaemonHandler:
    def __init__(self) -> None:
        self.application = BackupApplication()
        self.state = StateStore()

    def __call__(self, request: dict[str, Any]) -> dict[str, Any]:
        command = request.get("command")
        if command == "ping":
            return {"ok": True, "status": "ready"}
        if command == "status":
            return {"ok": True, "summary": self.state.latest_summary()}
        if command == "backup":
            raw_destination = request.get("destination")
            destination = Path(str(raw_destination)).expanduser() if raw_destination else None
            summary = self.application.backup(destination)
            return {"ok": summary.repositories_failed == 0, "summary": summary.to_dict()}
        return {"ok": False, "error": f"Unknown command: {command}"}


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="GitHub Backup Deck background daemon")
    parser.add_argument("--socket", type=Path, help="Override Unix socket path")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    with UnixIpcServer(DaemonHandler(), args.socket) as server:
        try:
            server.serve_forever(poll_interval=0.5)
        except KeyboardInterrupt:
            pass
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
