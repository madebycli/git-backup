from __future__ import annotations

import json
import os
import tempfile
from dataclasses import asdict, dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from github_backup_deck.models import BackupFormat, BackupOptions

APP_NAME = "github-backup-deck"


def _xdg_path(variable: str, fallback: Path) -> Path:
    raw = os.environ.get(variable)
    return Path(raw).expanduser() if raw else fallback


def config_dir() -> Path:
    return _xdg_path("XDG_CONFIG_HOME", Path.home() / ".config") / APP_NAME


def state_dir() -> Path:
    return _xdg_path("XDG_STATE_HOME", Path.home() / ".local" / "state") / APP_NAME


def cache_dir() -> Path:
    return _xdg_path("XDG_CACHE_HOME", Path.home() / ".cache") / APP_NAME


def runtime_dir() -> Path:
    raw = os.environ.get("XDG_RUNTIME_DIR")
    if raw:
        return Path(raw) / APP_NAME
    return Path(tempfile.gettempdir()) / f"{APP_NAME}-{os.getuid()}"


@dataclass(frozen=True, slots=True)
class AppConfig:
    default_backup_directory: str = "~/GitHub Backup"
    include_issues: bool = True
    include_pull_requests: bool = True
    include_releases: bool = True
    include_action_artifacts: bool = False
    include_archived: bool = True
    fetch_lfs: bool = True
    backup_format: BackupFormat = "zip"
    versioned_snapshots: bool = True

    @property
    def backup_path(self) -> Path:
        return Path(self.default_backup_directory).expanduser()

    @property
    def options(self) -> BackupOptions:
        return BackupOptions(
            include_issues=self.include_issues,
            include_pull_requests=self.include_pull_requests,
            include_releases=self.include_releases,
            include_action_artifacts=self.include_action_artifacts,
            include_archived=self.include_archived,
            fetch_lfs=self.fetch_lfs,
            backup_format=self.backup_format,
            versioned_snapshots=self.versioned_snapshots,
        )

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> "AppConfig":
        defaults = asdict(cls())
        values = {key: payload.get(key, default) for key, default in defaults.items()}
        values["default_backup_directory"] = str(values["default_backup_directory"])
        for key in (
            "include_issues",
            "include_pull_requests",
            "include_releases",
            "include_action_artifacts",
            "include_archived",
            "fetch_lfs",
            "versioned_snapshots",
        ):
            values[key] = values[key] if isinstance(values[key], bool) else bool(defaults[key])
        if values["backup_format"] not in {"zip", "folder"}:
            values["backup_format"] = "zip"
        return cls(**values)


class ConfigStore:
    def __init__(self, path: Path | None = None) -> None:
        self.path = path or config_dir() / "config.json"

    def load(self) -> AppConfig:
        if not self.path.exists():
            return AppConfig()
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise ValueError("configuration root is not an object")
            return AppConfig.from_dict(payload)
        except (OSError, json.JSONDecodeError, TypeError, ValueError):
            self._quarantine_invalid_config()
            return AppConfig()

    def _quarantine_invalid_config(self) -> None:
        timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        quarantine = self.path.with_name(f"{self.path.name}.invalid-{timestamp}")
        try:
            os.replace(self.path, quarantine)
        except OSError:
            return

    def save(self, config: AppConfig) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
        _atomic_write_json(self.path, asdict(config), mode=0o600)


def _atomic_write_json(path: Path, payload: object, mode: int = 0o600) -> None:
    data = json.dumps(payload, indent=2, sort_keys=True) + "\n"
    fd, temporary_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    temporary = Path(temporary_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)
