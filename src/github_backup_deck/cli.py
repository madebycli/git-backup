from __future__ import annotations

import argparse
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from github_backup_deck import __version__
from github_backup_deck.app import BackupApplication
from github_backup_deck.auth.github_cli import GitHubCliAuth
from github_backup_deck.backup.verifier import verify_destination
from github_backup_deck.config import ConfigStore, runtime_dir
from github_backup_deck.events import ProgressEvent
from github_backup_deck.ipc.client import IpcClient
from github_backup_deck.state import StateStore
from github_backup_deck.storage.probe import probe_path


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="github-backup-deck",
        description="Graphical GitHub backup manager for Wayland",
    )
    parser.add_argument("--version", action="version", version=__version__)
    subparsers = parser.add_subparsers(dest="command")
    subparsers.add_parser("gui", help="Open the layer-shell dashboard")
    subparsers.add_parser("login", help="Authenticate with GitHub CLI in a browser")
    backup = subparsers.add_parser("backup", help="Run a foreground backup")
    backup.add_argument("--destination", type=Path)
    subparsers.add_parser("cancel", help="Cancel the active background backup")
    subparsers.add_parser("status", help="Show background and latest backup status")
    subparsers.add_parser("overview", help="Open the layer-shell status overview")
    probe = subparsers.add_parser("probe", help="Test a backup destination")
    probe.add_argument("path", type=Path)
    verify = subparsers.add_parser("verify", help="Verify legacy mirror storage")
    verify.add_argument("--destination", type=Path)
    subparsers.add_parser("doctor", help="Check runtime dependencies and configuration")
    return parser


def _print_event(event: ProgressEvent) -> None:
    prefix = event.kind.upper()
    progress = ""
    if event.current is not None and event.total is not None:
        progress = f" [{event.current}/{event.total}]"
    repository = f" {event.repository}:" if event.repository else ""
    print(f"{prefix}{progress}{repository} {event.message}", file=sys.stderr)


def _json(payload: object) -> None:
    print(json.dumps(payload, indent=2, sort_keys=True))


def _schema_available(name: str) -> bool:
    try:
        import gi

        gi.require_version("Gio", "2.0")
        from gi.repository import Gio

        source = Gio.SettingsSchemaSource.get_default()
        return bool(source is not None and source.lookup(name, True) is not None)
    except Exception:
        return False


def _doctor() -> tuple[dict[str, Any], bool]:
    auth = GitHubCliAuth().status()
    config = ConfigStore().load()
    dependencies = {
        name: shutil.which(name)
        for name in ("gh", "git", "git-lfs", "notify-send", "xdg-open")
    }
    runtime = runtime_dir()
    schema_available = _schema_available("org.gtk.Settings.FileChooser")
    payload: dict[str, Any] = {
        "version": __version__,
        "python": sys.version.split()[0],
        "dependencies": dependencies,
        "github": {
            "authenticated": auth.authenticated,
            "login": auth.login,
            "note": auth.error,
        },
        "config_path": str(ConfigStore().path),
        "backup_directory": str(config.backup_path),
        "runtime_directory": str(runtime),
        "gtk_available": _module_available("gi"),
        "gtk_file_chooser_schema": schema_available,
    }
    required_ok = (
        dependencies["gh"] is not None
        and dependencies["git"] is not None
        and dependencies["git-lfs"] is not None
        and schema_available
    )
    payload["ok"] = required_ok
    return payload, required_ok


def _module_available(name: str) -> bool:
    try:
        __import__(name)
    except ImportError:
        return False
    return True


def _background_status() -> dict[str, Any]:
    client = IpcClient()
    if client.ping():
        return client.request({"command": "status", "after_sequence": 0})
    return {
        "ok": True,
        "job": {"state": "offline", "message": "Background service is not running"},
        "latest_summary": StateStore().latest_summary(),
    }


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    command = args.command or "gui"
    try:
        if command == "gui":
            from github_backup_deck.gui.main_window import run_gui

            return run_gui()
        if command == "overview":
            from github_backup_deck.gui.overview import main as overview_main

            return overview_main()
        if command == "login":
            status = GitHubCliAuth().login()
            _json(
                {
                    "authenticated": status.authenticated,
                    "login": status.login,
                    "error": status.error,
                }
            )
            return 0 if status.authenticated else 1
        if command == "backup":
            summary = BackupApplication().backup(args.destination, sink=_print_event)
            _json(summary.to_dict())
            return 0 if summary.repositories_failed == 0 and summary.snapshot_path else 1
        if command == "cancel":
            client = IpcClient()
            if not client.ping():
                _json({"ok": False, "error": "Background service is not running"})
                return 1
            response = client.request({"command": "cancel_backup"})
            _json(response)
            return 0 if response.get("ok") else 1
        if command == "status":
            _json(_background_status())
            return 0
        if command == "probe":
            probe_result = probe_path(args.path)
            _json(probe_result.to_dict())
            return 0 if probe_result.ok else 1
        if command == "verify":
            config = ConfigStore().load()
            destination = args.destination or config.backup_path
            verification_result = verify_destination(destination)
            _json(verification_result.to_dict())
            return 0 if verification_result.ok else 1
        if command == "doctor":
            payload, required_ok = _doctor()
            _json(payload)
            return 0 if required_ok else 1
    except KeyboardInterrupt:
        return 130
    parser.error(f"Unknown command: {command}")
    return 2
